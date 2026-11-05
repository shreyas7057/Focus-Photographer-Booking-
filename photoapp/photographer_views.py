# Views for the photographer panel/dashboard: profile, portfolio, team, services,
# packages, availability calendar, bookings, enquiries, invoices and exports.

import csv
from datetime import date, timedelta
from functools import wraps
from io import BytesIO

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import get_template
from django.utils import timezone
from django.views.decorators.http import require_POST
from xhtml2pdf import pisa

from .models import (
    Album, AvailableDate, Booking, Category, Enquiry, Gallery,
    Invoice, Package, Photographer, Service, Stat, Team,
)

User = get_user_model()

TEMPLATE_DIR = 'customadmin/photographer/'

# Which status changes a photographer is allowed to make
BOOKING_TRANSITIONS = {
    Booking.STATUS_REQUESTED: {Booking.STATUS_ACCEPTED, Booking.STATUS_REJECTED},
    Booking.STATUS_ACCEPTED: {Booking.STATUS_COMPLETED, Booking.STATUS_REJECTED},
}


# ---------------------------------------------------------------
# Access control
# ---------------------------------------------------------------
def photographer_required(view_func):
    """Logged in AND user_type is Photographer."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'Please log in to continue.')
            return redirect('login-user')
        if request.user.user_type != User.PHOTOGRAPHER:
            messages.error(request, 'This page is only for photographers.')
            return redirect('/')
        return view_func(request, *args, **kwargs)
    return wrapper


def profile_required(view_func):
    """Photographer who has already filled in the profile. Sets request.photographer."""
    @photographer_required
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        try:
            request.photographer = request.user.photographer_profile
        except Photographer.DoesNotExist:
            messages.info(request, 'Please complete your profile first.')
            return redirect('add_photographer_info')
        return view_func(request, *args, **kwargs)
    return wrapper


# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------
def _to_int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_date(value):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _is_image(uploaded_file):
    return uploaded_file is not None and uploaded_file.content_type.startswith('image/')


def _flash_errors(request, error):
    for field, errors in error.message_dict.items():
        for message in errors:
            label = '' if field == '__all__' else f"{field.replace('_', ' ').title()}: "
            messages.error(request, f'{label}{message}')


def _category_ids(request):
    return [int(i) for i in request.POST.getlist('categories') if i.isdigit()]


def _send_mail(subject, message, recipients):
    recipients = list({r for r in recipients if r})
    if recipients:
        send_mail(subject, message, settings.EMAIL_HOST_USER, recipients, fail_silently=True)


def _render_pdf(template_name, context):
    html = get_template(template_name).render(context)
    buffer = BytesIO()
    result = pisa.pisaDocument(BytesIO(html.encode('UTF-8')), buffer)
    if result.err:
        return HttpResponse('Error generating PDF', status=500)
    return HttpResponse(buffer.getvalue(), content_type='application/pdf')


# ---------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------
@profile_required
def custom_photographer_index(request):
    photographer = request.photographer
    today = timezone.localdate()
    bookings = photographer.bookings

    context = {
        'photographer': photographer,
        'bookings': bookings.count(),
        'pending_requests': bookings.filter(status=Booking.STATUS_REQUESTED).count(),
        'open_enquiries': photographer.enquiries.filter(status=Enquiry.STATUS_OPEN).count(),
        'todays_bookings': bookings.filter(
            status=Booking.STATUS_ACCEPTED, start_date__lte=today, end_date__gte=today
        ).select_related('customer__user'),
        'upcoming_bookings': bookings.filter(
            status=Booking.STATUS_ACCEPTED, start_date__gt=today
        ).select_related('customer__user').order_by('start_date')[:5],
        'recent_requests': bookings.filter(
            status=Booking.STATUS_REQUESTED
        ).select_related('customer__user')[:5],
    }
    return render(request, TEMPLATE_DIR + 'photo_index.html', context)


# ---------------------------------------------------------------
# Profile
# ---------------------------------------------------------------
@photographer_required
def add_photographer_info(request):
    if Photographer.objects.filter(user=request.user).exists():
        messages.info(request, 'Your profile already exists. You can edit it here.')
        return redirect('edit_photographer_info')

    categories = Category.objects.all()

    if request.method == 'POST':
        photographer = Photographer(
            user=request.user,
            location=request.POST.get('location', '').strip(),
            studio_name=request.POST.get('studio_name', '').strip(),
            mobile=request.POST.get('mobile', '').strip(),
            address=request.POST.get('address', '').strip(),
            bio=request.POST.get('bio', '').strip(),
            experience_years=_to_int(request.POST.get('experience_years'), 0),
            cover_photo=request.FILES.get('cover_photo'),
            your_photo=request.FILES.get('your_photo'),
        )
        try:
            photographer.full_clean()
        except ValidationError as error:
            _flash_errors(request, error)
            return render(request, TEMPLATE_DIR + 'add_photographer_info.html',
                          {'categories': categories, 'form_data': request.POST})

        photographer.save()
        photographer.categories.set(Category.objects.filter(pk__in=_category_ids(request)))
        messages.success(request, 'Information added successfully!')
        return redirect('custom_photographer_index')

    return render(request, TEMPLATE_DIR + 'add_photographer_info.html', {'categories': categories})


@profile_required
def view_photographer_info(request):
    return render(request, TEMPLATE_DIR + 'view_photographer_info.html',
                  {'photographer': request.photographer})


@profile_required
def edit_photographer_info(request):
    photographer = request.photographer
    return render(request, TEMPLATE_DIR + 'edit_photographer_info.html', {
        'photographer': photographer,
        'categories': Category.objects.all(),
        'selected_categories': list(photographer.categories.values_list('id', flat=True)),
    })


@profile_required
def update_photographer_info(request):
    if request.method != 'POST':
        return redirect('edit_photographer_info')

    photographer = request.photographer
    photographer.location = request.POST.get('location', '').strip()
    photographer.studio_name = request.POST.get('studio_name', '').strip()
    photographer.mobile = request.POST.get('mobile', '').strip()
    photographer.address = request.POST.get('address', '').strip()
    photographer.bio = request.POST.get('bio', '').strip()
    photographer.experience_years = _to_int(request.POST.get('experience_years'), 0)

    # only replace images when a new file was actually uploaded
    cover_photo = request.FILES.get('cover_photo')
    your_photo = request.FILES.get('your_photo')
    if cover_photo:
        photographer.cover_photo = cover_photo
    if your_photo:
        photographer.your_photo = your_photo

    try:
        photographer.full_clean()
    except ValidationError as error:
        _flash_errors(request, error)
        return redirect('edit_photographer_info')

    photographer.save()
    photographer.categories.set(Category.objects.filter(pk__in=_category_ids(request)))
    messages.success(request, 'Photographer information updated.')
    return redirect('view_photographer_info')


# ---------------------------------------------------------------
# Stats (one row per photographer: add the first time, update after)
# ---------------------------------------------------------------
@profile_required
def stat_add(request):
    photographer = request.photographer

    if request.method == 'POST':
        values = {name: _to_int(request.POST.get(name))
                  for name in ('projects', 'customers', 'albums', 'completed')}
        if any(v is None or v < 0 for v in values.values()):
            messages.error(request, 'Enter valid whole numbers (0 or more) for every field.')
            return redirect('stat_add')

        Stat.objects.update_or_create(photographer=photographer, defaults=values)
        messages.success(request, 'Stats saved successfully!')
        return redirect('custom_photographer_index')

    stat = Stat.objects.filter(photographer=photographer).first()
    return render(request, TEMPLATE_DIR + 'add_stat.html', {'stat': stat})


@profile_required
def view_stat(request):
    stat = Stat.objects.filter(photographer=request.photographer).first()
    if stat is None:
        messages.info(request, 'Add your stats first.')
        return redirect('stat_add')
    return render(request, TEMPLATE_DIR + 'view_stat.html', {'stat': stat})


# ---------------------------------------------------------------
# Portfolio: albums + gallery photos
# ---------------------------------------------------------------
@profile_required
def add_album(request):
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        if not title:
            messages.error(request, 'Album title is required.')
            return redirect('add_album')

        Album.objects.create(
            photographer=request.photographer,
            title=title,
            description=request.POST.get('description', '').strip(),
            category=Category.objects.filter(pk=_to_int(request.POST.get('category'))).first(),
        )
        messages.success(request, 'Album created successfully!')
        return redirect('view_albums')

    return render(request, TEMPLATE_DIR + 'add_album.html', {'categories': Category.objects.all()})


@profile_required
def view_albums(request):
    albums = request.photographer.albums.select_related('category')
    return render(request, TEMPLATE_DIR + 'view_albums.html', {'albums': albums})


@profile_required
@require_POST
def delete_album(request, id):
    album = get_object_or_404(Album, id=id, photographer=request.photographer)
    album.delete()   # photos stay in the gallery, they just lose the album
    messages.success(request, 'Album deleted successfully!')
    return redirect('view_albums')


@profile_required
def add_gallery(request):
    photographer = request.photographer
    albums = photographer.albums.all()

    if request.method == 'POST':
        photos = request.FILES.getlist('photo')
        if not photos:
            messages.error(request, 'Choose at least one image.')
            return redirect('add_gallery')
        if not all(_is_image(p) for p in photos):
            messages.error(request, 'Only image files can be uploaded.')
            return redirect('add_gallery')

        album = albums.filter(pk=_to_int(request.POST.get('album'))).first()
        caption = request.POST.get('caption', '').strip()[:200]
        is_featured = request.POST.get('is_featured') == 'on'

        for photo in photos:
            Gallery.objects.create(photographer=photographer, album=album, photo=photo,
                                   caption=caption, is_featured=is_featured)
        messages.success(request, f'{len(photos)} image(s) added successfully.')
        return redirect('view_gallery')

    return render(request, TEMPLATE_DIR + 'add_gallery.html', {'albums': albums})


@profile_required
def view_gallery(request):
    gallery = request.photographer.gallery_images.select_related('album')
    return render(request, TEMPLATE_DIR + 'view_gallery.html', {'gallery': gallery})


@profile_required
@require_POST
def delete_gallery(request, id):
    photo = get_object_or_404(Gallery, id=id, photographer=request.photographer)
    photo.delete()
    messages.success(request, 'Image deleted successfully!')
    return redirect('view_gallery')


# ---------------------------------------------------------------
# Team
# ---------------------------------------------------------------
@profile_required
def add_team(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        speciality = request.POST.get('speciality', '').strip()
        image = request.FILES.get('image')

        if not name or not speciality:
            messages.error(request, 'Name and speciality are required.')
            return redirect('add_team')
        if image and not _is_image(image):
            messages.error(request, 'Only image files can be uploaded.')
            return redirect('add_team')

        Team.objects.create(photographer=request.photographer, image=image,
                            name=name, speciality=speciality)
        messages.success(request, 'Team member added successfully!')
        return redirect('view_team')

    return render(request, TEMPLATE_DIR + 'add_team.html')


@profile_required
def view_team(request):
    return render(request, TEMPLATE_DIR + 'view_team.html',
                  {'team': request.photographer.team_members.all()})


@profile_required
@require_POST
def delete_team(request, id):
    member = get_object_or_404(Team, id=id, photographer=request.photographer)
    member.delete()
    messages.success(request, 'Team member deleted successfully!')
    return redirect('view_team')


# ---------------------------------------------------------------
# Services
# ---------------------------------------------------------------
@profile_required
def add_service(request):
    if request.method == 'POST':
        service_type = request.POST.get('serviceType', '').strip()
        description = request.POST.get('description', '').strip()
        if not service_type or not description:
            messages.error(request, 'Service type and description are required.')
            return redirect('add_service')

        Service.objects.create(photographer=request.photographer,
                               serviceType=service_type, description=description)
        messages.success(request, 'Service added successfully!')
        return redirect('view_service')

    return render(request, TEMPLATE_DIR + 'add_service.html')


@profile_required
def view_service(request):
    return render(request, TEMPLATE_DIR + 'view_service.html',
                  {'service': request.photographer.services.all()})


@profile_required
@require_POST
def delete_service(request, id):
    service = get_object_or_404(Service, id=id, photographer=request.photographer)
    service.delete()
    messages.success(request, 'Service deleted successfully!')
    return redirect('view_service')


# ---------------------------------------------------------------
# Packages
# ---------------------------------------------------------------
@profile_required
def add_package(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        price = _to_int(request.POST.get('price'))

        if not name or not description or price is None or price <= 0:
            messages.error(request, 'Name, description and a price above 0 are required.')
            return redirect('add_package')

        Package.objects.create(photographer=request.photographer, name=name,
                               description=description, price=price)
        messages.success(request, 'Package added successfully!')
        return redirect('view_package')

    return render(request, TEMPLATE_DIR + 'add_package.html')


@profile_required
def view_package(request):
    return render(request, TEMPLATE_DIR + 'view_package.html',
                  {'package': request.photographer.packages.all()})


@profile_required
@require_POST
def delete_package(request, id):
    package = get_object_or_404(Package, id=id, photographer=request.photographer)
    package.delete()
    messages.success(request, 'Package deleted successfully!')
    return redirect('view_package')


# ---------------------------------------------------------------
# Availability calendar (dates customers are allowed to book)
# ---------------------------------------------------------------
@profile_required
def manage_availability(request):
    photographer = request.photographer
    today = timezone.localdate()

    if request.method == 'POST':
        start = _parse_date(request.POST.get('start_date'))
        end = _parse_date(request.POST.get('end_date')) or start

        if not start or not end or end < start:
            messages.error(request, 'Choose a valid start date and an end date on or after it.')
        elif start < today:
            messages.error(request, 'You cannot add dates in the past.')
        elif (end - start).days > 365:
            messages.error(request, 'Add at most one year of dates at a time.')
        else:
            existing = set(photographer.available_dates
                           .filter(date__range=(start, end)).values_list('date', flat=True))
            all_days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
            new_dates = [AvailableDate(photographer=photographer, date=d)
                         for d in all_days if d not in existing]
            AvailableDate.objects.bulk_create(new_dates)
            messages.success(request, f'{len(new_dates)} date(s) added to your calendar.')
        return redirect('manage_availability')

    dates = photographer.available_dates.filter(date__gte=today)
    return render(request, TEMPLATE_DIR + 'manage_availability.html',
                  {'dates': dates, 'today': today})


@profile_required
@require_POST
def delete_availability(request, id):
    slot = get_object_or_404(AvailableDate, id=id, photographer=request.photographer)
    if slot.is_booked:
        messages.error(request, 'That date is already booked and cannot be removed.')
    else:
        slot.delete()
        messages.success(request, 'Date removed from your calendar.')
    return redirect('manage_availability')


# ---------------------------------------------------------------
# Bookings (requests come from customers; the photographer responds)
# ---------------------------------------------------------------
@profile_required
def view_booking(request):
    status = request.GET.get('status', '')
    booking = request.photographer.bookings.select_related('customer__user')
    if status in dict(Booking.BOOKING_STATUS):
        booking = booking.filter(status=status)

    return render(request, TEMPLATE_DIR + 'view_booking.html', {
        'booking': booking,
        'status': status,
        'status_choices': Booking.BOOKING_STATUS,
    })


@profile_required
def booking_detail(request, id):
    booking = get_object_or_404(
        Booking.objects.select_related('customer__user', 'package'),
        id=id, photographer=request.photographer)
    return render(request, TEMPLATE_DIR + 'booking_detail.html', {
        'booking': booking,
        'invoice': getattr(booking, 'invoice', None),
        'allowed_statuses': BOOKING_TRANSITIONS.get(booking.status, set()),
    })


@profile_required
@require_POST
def update_booking_status(request, id):
    photographer = request.photographer
    booking = get_object_or_404(
        Booking.objects.select_related('customer__user'), id=id, photographer=photographer)
    new_status = request.POST.get('status')

    if new_status not in BOOKING_TRANSITIONS.get(booking.status, set()):
        messages.error(request, f'A {booking.status.lower()} booking cannot be changed to {new_status}.')
        return redirect('booking_detail', id=id)

    with transaction.atomic():
        if new_status == Booking.STATUS_ACCEPTED:
            # Every shoot day must be a free date in the calendar. This also stops double booking.
            days_needed = (booking.end_date - booking.start_date).days + 1
            free_slots = list(AvailableDate.objects.select_for_update().filter(
                photographer=photographer,
                date__range=(booking.start_date, booking.end_date),
                is_booked=False,
            ))
            if len(free_slots) != days_needed:
                messages.error(request, 'Every date of this shoot must be free in your availability '
                                        'calendar before you can accept it.')
                return redirect('booking_detail', id=id)
            AvailableDate.objects.filter(pk__in=[s.pk for s in free_slots]).update(is_booked=True)

        elif booking.status == Booking.STATUS_ACCEPTED and new_status == Booking.STATUS_REJECTED:
            # an accepted booking is being cancelled by the photographer: free the dates again
            AvailableDate.objects.filter(
                photographer=photographer,
                date__range=(booking.start_date, booking.end_date),
            ).update(is_booked=False)

        booking.status = new_status
        booking.save(update_fields=['status', 'updated_at'])

    _send_mail(
        subject=f'Your booking #{booking.id} is now {new_status}',
        message=(f'Hello {booking.name},\n\n'
                 f'{photographer.studio_name} has marked your booking '
                 f'({booking.start_date} to {booking.end_date}) as {new_status}.\n'),
        recipients=[booking.email, booking.customer.user.email],
    )
    messages.success(request, f'Booking #{booking.id} marked as {new_status}.')
    return redirect('booking_detail', id=id)


@profile_required
@require_POST
def delete_booking(request, id):
    booking = get_object_or_404(Booking, id=id, photographer=request.photographer)
    if booking.status == Booking.STATUS_ACCEPTED:
        messages.error(request, 'Reject or complete an accepted booking before deleting it.')
        return redirect('view_booking')
    booking.delete()
    messages.success(request, 'Booking deleted successfully!')
    return redirect('view_booking')


@profile_required
def export_booking_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="booking.csv"'

    writer = csv.writer(response)
    writer.writerow(['ID', 'Customer', 'Name', 'Email', 'Mobile', 'Start Date', 'End Date',
                     'Address', 'No. of Days', 'Comment', 'Status', 'Created At'])

    rows = request.photographer.bookings.values_list(
        'id', 'customer__user__full_name', 'name', 'email', 'mobile', 'start_date', 'end_date',
        'address', 'no_of_days', 'comment', 'status', 'created_at')
    for row in rows:
        writer.writerow(row)
    return response


@profile_required
def export_booking_pdf(request):
    photographer = request.photographer
    booking = photographer.bookings.select_related('customer__user')
    return _render_pdf(TEMPLATE_DIR + 'pdf_booking.html',
                       {'booking': booking, 'photographer': photographer})


# ---------------------------------------------------------------
# Enquiries
# ---------------------------------------------------------------
@profile_required
def view_enquiries(request):
    status = request.GET.get('status', '')
    enquiries = request.photographer.enquiries.select_related('customer__user')
    if status in dict(Enquiry.ENQUIRY_STATUS):
        enquiries = enquiries.filter(status=status)

    return render(request, TEMPLATE_DIR + 'view_enquiries.html', {
        'enquiries': enquiries,
        'status': status,
        'status_choices': Enquiry.ENQUIRY_STATUS,
    })


@profile_required
def reply_enquiry(request, id):
    enquiry = get_object_or_404(
        Enquiry.objects.select_related('customer__user'), id=id, photographer=request.photographer)

    if request.method == 'POST':
        reply = request.POST.get('reply', '').strip()
        if not reply:
            messages.error(request, 'Write a reply before sending.')
            return redirect('reply_enquiry', id=id)

        enquiry.reply = reply
        enquiry.status = Enquiry.STATUS_RESPONDED
        enquiry.save(update_fields=['reply', 'status'])

        _send_mail(
            subject=f'Reply to your enquiry from {request.photographer.studio_name}',
            message=f'Hello {enquiry.customer.user.full_name},\n\n{reply}\n',
            recipients=[enquiry.customer.user.email],
        )
        messages.success(request, 'Reply sent.')
        return redirect('view_enquiries')

    return render(request, TEMPLATE_DIR + 'reply_enquiry.html', {'enquiry': enquiry})


@profile_required
@require_POST
def close_enquiry(request, id):
    enquiry = get_object_or_404(Enquiry, id=id, photographer=request.photographer)
    enquiry.status = Enquiry.STATUS_CLOSED
    enquiry.save(update_fields=['status'])
    messages.success(request, 'Enquiry closed.')
    return redirect('view_enquiries')


# ---------------------------------------------------------------
# Invoices
# ---------------------------------------------------------------
@profile_required
def generate_invoice(request, id):
    photographer = request.photographer
    booking = get_object_or_404(Booking, id=id, photographer=photographer)

    if hasattr(booking, 'invoice'):
        messages.info(request, 'An invoice already exists for this booking.')
        return redirect('get_invoice')
    if booking.status not in (Booking.STATUS_ACCEPTED, Booking.STATUS_COMPLETED):
        messages.error(request, 'You can only invoice accepted or completed bookings.')
        return redirect('booking_detail', id=id)

    packages = photographer.packages.all()

    if request.method == 'POST':
        package = get_object_or_404(Package, id=_to_int(request.POST.get('package')),
                                    photographer=photographer)
        extra_amt = _to_int(request.POST.get('extra_amt'), 0)
        payment_status = request.POST.get('payment_status', 'Pending')

        if extra_amt < 0:
            messages.error(request, 'Extra amount cannot be negative.')
            return redirect('generate_invoice', id=id)
        if payment_status not in dict(Invoice.PAYMENT_STATUS):
            payment_status = 'Pending'

        Invoice.objects.create(photographer=photographer, booking=booking, package=package,
                               extra_amt=extra_amt, payment_status=payment_status)
        messages.success(request, 'Invoice generated successfully!')
        return redirect('get_invoice')

    return render(request, TEMPLATE_DIR + 'generate_invoice.html', {
        'package': packages,
        'booking': booking,
        'payment_choices': Invoice.PAYMENT_STATUS,
    })


@profile_required
def get_invoice(request):
    invoices = request.photographer.invoices.select_related('booking', 'package')
    return render(request, TEMPLATE_DIR + 'all_invoices.html', {'invoices': invoices})


@profile_required
@require_POST
def mark_invoice_paid(request, id):
    invoice = get_object_or_404(Invoice, id=id, photographer=request.photographer)
    invoice.payment_status = 'Paid'
    invoice.save()
    messages.success(request, 'Invoice marked as paid.')
    return redirect('get_invoice')


@profile_required
def download_invoice_pdf(request, id):
    invoice = get_object_or_404(
        Invoice.objects.select_related('booking', 'package', 'photographer__user'),
        id=id, photographer=request.photographer)
    return _render_pdf(TEMPLATE_DIR + 'download_invoice_pdf.html', {'invoice': invoice})