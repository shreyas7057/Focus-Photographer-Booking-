from functools import wraps

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import (
    AvailableDate, Booking, Category, Customer, Enquiry, Photographer,
)

User = get_user_model()


# ---------------------------------------------------------------
# Access control + helpers
# ---------------------------------------------------------------
def admin_required(view_func):
    """Only logged-in users whose user_type is Admin can open the view."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'Please log in to continue.')
            return redirect('login-user')
        if request.user.user_type != User.ADMIN:
            messages.error(request, 'You do not have permission to open that page.')
            return redirect('/')
        return view_func(request, *args, **kwargs)
    return wrapper


def _paginate(request, queryset, per_page=10):
    return Paginator(queryset, per_page).get_page(request.GET.get('page'))


def _set_dates_booked(booking, booked):
    AvailableDate.objects.filter(
        photographer=booking.photographer,
        date__range=(booking.start_date, booking.end_date),
    ).update(is_booked=booked)


def _overlaps_accepted(booking):
    return Booking.objects.filter(
        photographer=booking.photographer,
        status=Booking.STATUS_ACCEPTED,
        start_date__lte=booking.end_date,
        end_date__gte=booking.start_date,
    ).exclude(pk=booking.pk).exists()


# ---------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------
@admin_required
def custom_admin_index(request):
    status_counts = dict(
        Booking.objects.order_by().values_list('status').annotate(total=Count('id'))
    )
    context = {
        'total_photographers': Photographer.objects.count(),
        'total_customers': Customer.objects.count(),
        'total_bookings': Booking.objects.count(),
        'open_enquiries': Enquiry.objects.filter(status=Enquiry.STATUS_OPEN).count(),
        'requested': status_counts.get(Booking.STATUS_REQUESTED, 0),
        'accepted': status_counts.get(Booking.STATUS_ACCEPTED, 0),
        'completed': status_counts.get(Booking.STATUS_COMPLETED, 0),
        'rejected': status_counts.get(Booking.STATUS_REJECTED, 0),
        'cancelled': status_counts.get(Booking.STATUS_CANCELLED, 0),
        'recent_bookings': Booking.objects.select_related(
            'customer__user', 'photographer__user')[:5],
        'recent_photographers': Photographer.objects.select_related('user').order_by('-created_at')[:5],
    }
    return render(request, 'admin_panel/dashboard.html', context)


# ---------------------------------------------------------------
# Photographers
# ---------------------------------------------------------------
@admin_required
def admin_photographers(request):
    q = request.GET.get('q', '').strip()
    state = request.GET.get('status', '')

    photographers = Photographer.objects.select_related('user').order_by('-created_at')
    if q:
        photographers = photographers.filter(
            Q(user__full_name__icontains=q) | Q(user__email__icontains=q) |
            Q(studio_name__icontains=q) | Q(location__icontains=q)
        )
    if state == 'active':
        photographers = photographers.filter(user__is_active=True)
    elif state == 'inactive':
        photographers = photographers.filter(user__is_active=False)

    return render(request, 'admin_panel/photographers.html', {
        'page_obj': _paginate(request, photographers),
        'q': q,
        'state': state,
    })


@admin_required
def admin_photographer_detail(request, pk):
    photographer = get_object_or_404(Photographer.objects.select_related('user'), pk=pk)
    return render(request, 'admin_panel/photographer_detail.html', {
        'photographer': photographer,
        'services': photographer.services.all(),
        'packages': photographer.packages.all(),
        'gallery_count': photographer.gallery_images.count(),
        'bookings': photographer.bookings.select_related('customer__user')[:10],
    })


@admin_required
@require_POST
def admin_photographer_toggle(request, pk):
    """Approve / block a photographer by flipping the user's is_active flag."""
    photographer = get_object_or_404(Photographer.objects.select_related('user'), pk=pk)
    user = photographer.user
    user.is_active = not user.is_active
    user.save(update_fields=['is_active'])
    state = 'activated' if user.is_active else 'deactivated'
    messages.success(request, f'{user.full_name} has been {state}.')
    return redirect(request.POST.get('next') or 'admin-photographers')


@admin_required
@require_POST
def admin_photographer_delete(request, pk):
    photographer = get_object_or_404(Photographer.objects.select_related('user'), pk=pk)
    name = photographer.user.full_name
    photographer.user.delete()   # cascades to the profile, gallery, bookings, etc.
    messages.success(request, f'{name} was deleted.')
    return redirect('admin-photographers')


# ---------------------------------------------------------------
# Customers
# ---------------------------------------------------------------
@admin_required
def admin_customers(request):
    q = request.GET.get('q', '').strip()
    state = request.GET.get('status', '')

    customers = Customer.objects.select_related('user').annotate(
        booking_count=Count('bookings')
    ).order_by('-created_at')
    if q:
        customers = customers.filter(
            Q(user__full_name__icontains=q) | Q(user__email__icontains=q) |
            Q(mobile__icontains=q) | Q(city__icontains=q)
        )
    if state == 'active':
        customers = customers.filter(user__is_active=True)
    elif state == 'inactive':
        customers = customers.filter(user__is_active=False)

    return render(request, 'admin_panel/customers.html', {
        'page_obj': _paginate(request, customers),
        'q': q,
        'state': state,
    })


@admin_required
def admin_customer_detail(request, pk):
    customer = get_object_or_404(Customer.objects.select_related('user'), pk=pk)
    return render(request, 'admin_panel/customer_detail.html', {
        'customer': customer,
        'bookings': customer.bookings.select_related('photographer__user'),
        'enquiries': customer.enquiries.select_related('photographer__user'),
    })


@admin_required
@require_POST
def admin_customer_toggle(request, pk):
    customer = get_object_or_404(Customer.objects.select_related('user'), pk=pk)
    user = customer.user
    user.is_active = not user.is_active
    user.save(update_fields=['is_active'])
    state = 'activated' if user.is_active else 'blocked'
    messages.success(request, f'{user.full_name} has been {state}.')
    return redirect(request.POST.get('next') or 'admin-customers')


@admin_required
@require_POST
def admin_customer_delete(request, pk):
    customer = get_object_or_404(Customer.objects.select_related('user'), pk=pk)
    name = customer.user.full_name
    customer.user.delete()
    messages.success(request, f'{name} was deleted.')
    return redirect('admin-customers')


# ---------------------------------------------------------------
# Bookings
# ---------------------------------------------------------------
@admin_required
def admin_bookings(request):
    q = request.GET.get('q', '').strip()
    status = request.GET.get('status', '')

    bookings = Booking.objects.select_related('customer__user', 'photographer__user')
    if q:
        bookings = bookings.filter(
            Q(customer__user__full_name__icontains=q) |
            Q(photographer__user__full_name__icontains=q) |
            Q(name__icontains=q) | Q(email__icontains=q)
        )
    if status in dict(Booking.BOOKING_STATUS):
        bookings = bookings.filter(status=status)

    return render(request, 'admin_panel/bookings.html', {
        'page_obj': _paginate(request, bookings),
        'q': q,
        'status': status,
        'status_choices': Booking.BOOKING_STATUS,
    })


@admin_required
def admin_booking_detail(request, pk):
    booking = get_object_or_404(
        Booking.objects.select_related('customer__user', 'photographer__user', 'package'), pk=pk)
    return render(request, 'admin_panel/booking_detail.html', {
        'booking': booking,
        'invoice': getattr(booking, 'invoice', None),
        'status_choices': Booking.BOOKING_STATUS,
    })


@admin_required
@require_POST
def admin_booking_status(request, pk):
    """Admin override of a booking's status (disputes, fixes, etc.)."""
    booking = get_object_or_404(Booking.objects.select_related('photographer__user'), pk=pk)
    new_status = request.POST.get('status')

    if new_status not in dict(Booking.BOOKING_STATUS):
        messages.error(request, 'Invalid status.')
        return redirect('admin-booking-detail', pk=pk)

    if new_status == Booking.STATUS_ACCEPTED and _overlaps_accepted(booking):
        messages.error(request, 'This photographer already has an accepted booking on those dates.')
        return redirect('admin-booking-detail', pk=pk)

    with transaction.atomic():
        was_accepted = booking.status == Booking.STATUS_ACCEPTED
        booking.status = new_status
        booking.save(update_fields=['status', 'updated_at'])

        if new_status == Booking.STATUS_ACCEPTED:
            _set_dates_booked(booking, True)
        elif was_accepted and new_status in (Booking.STATUS_REJECTED, Booking.STATUS_CANCELLED):
            _set_dates_booked(booking, False)

    messages.success(request, f'Booking #{booking.id} marked as {new_status}.')
    return redirect('admin-booking-detail', pk=pk)


# ---------------------------------------------------------------
# Enquiries (read-only overview)
# ---------------------------------------------------------------
@admin_required
def admin_enquiries(request):
    status = request.GET.get('status', '')
    enquiries = Enquiry.objects.select_related('customer__user', 'photographer__user')
    if status in dict(Enquiry.ENQUIRY_STATUS):
        enquiries = enquiries.filter(status=status)

    return render(request, 'admin_panel/enquiries.html', {
        'page_obj': _paginate(request, enquiries),
        'status': status,
        'status_choices': Enquiry.ENQUIRY_STATUS,
    })


# ---------------------------------------------------------------
# Categories (shoot types used for search and filtering)
# ---------------------------------------------------------------
@admin_required
def admin_categories(request):
    categories = Category.objects.annotate(photographer_count=Count('photographers'))
    return render(request, 'admin_panel/categories.html', {'categories': categories})


@admin_required
def admin_category_add(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, 'Category name is required.')
        elif Category.objects.filter(name__iexact=name).exists():
            messages.error(request, 'That category already exists.')
        else:
            Category.objects.create(name=name)
            messages.success(request, f'Category "{name}" added.')
            return redirect('admin-categories')
    return render(request, 'admin_panel/category_form.html', {'title': 'Add Category'})


@admin_required
def admin_category_edit(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, 'Category name is required.')
        elif Category.objects.filter(name__iexact=name).exclude(pk=pk).exists():
            messages.error(request, 'That category already exists.')
        else:
            category.name = name
            category.save()
            messages.success(request, 'Category updated.')
            return redirect('admin-categories')
    return render(request, 'admin_panel/category_form.html', {
        'title': 'Edit Category',
        'category': category,
    })


@admin_required
@require_POST
def admin_category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    category.delete()
    messages.success(request, 'Category deleted.')
    return redirect('admin-categories')