from django.contrib import admin, messages

from .models import (
    Album, AvailableDate, Booking, Category, Customer, Enquiry,
    Gallery, Invoice, Package, Photographer, Service, Stat, Team,
)


# ---------------------------------------------------------------
# Shared
# ---------------------------------------------------------------
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


# ---------------------------------------------------------------
# Photographer side
# ---------------------------------------------------------------
class ServiceInline(admin.TabularInline):
    model = Service
    extra = 0


class PackageInline(admin.TabularInline):
    model = Package
    extra = 0


class TeamInline(admin.TabularInline):
    model = Team
    extra = 0


class GalleryInline(admin.TabularInline):
    model = Gallery
    extra = 0
    fields = ('photo', 'caption', 'album', 'is_featured')


@admin.register(Photographer)
class PhotographerAdmin(admin.ModelAdmin):
    list_display = ('user', 'studio_name', 'location', 'mobile', 'experience_years', 'created_at')
    list_filter = ('location', 'categories')
    search_fields = ('user__full_name', 'user__email', 'studio_name', 'location', 'mobile')
    filter_horizontal = ('categories',)
    readonly_fields = ('created_at',)
    list_select_related = ('user',)
    inlines = [ServiceInline, PackageInline, TeamInline, GalleryInline]


@admin.register(Album)
class AlbumAdmin(admin.ModelAdmin):
    list_display = ('title', 'photographer', 'category', 'created_at')
    list_filter = ('category',)
    search_fields = ('title', 'photographer__user__full_name', 'photographer__studio_name')
    list_select_related = ('photographer__user', 'category')


@admin.register(Gallery)
class GalleryAdmin(admin.ModelAdmin):
    list_display = ('photographer', 'album', 'caption', 'is_featured', 'uploaded_at')
    list_filter = ('is_featured',)
    list_editable = ('is_featured',)
    search_fields = ('photographer__user__full_name', 'caption')
    list_select_related = ('photographer__user', 'album')


@admin.register(Stat)
class StatAdmin(admin.ModelAdmin):
    list_display = ('photographer', 'projects', 'customers', 'albums', 'completed')


@admin.register(AvailableDate)
class AvailableDateAdmin(admin.ModelAdmin):
    list_display = ('photographer', 'date', 'is_booked')
    list_filter = ('is_booked', 'date')
    search_fields = ('photographer__user__full_name',)
    date_hierarchy = 'date'
    list_select_related = ('photographer__user',)


# ---------------------------------------------------------------
# Customer side
# ---------------------------------------------------------------
class CustomerBookingInline(admin.TabularInline):
    model = Booking
    extra = 0
    can_delete = False
    fields = ('photographer', 'start_date', 'end_date', 'status')
    readonly_fields = ('photographer', 'start_date', 'end_date', 'status')
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('user', 'mobile', 'city', 'total_bookings', 'created_at')
    list_filter = ('city',)
    search_fields = ('user__full_name', 'user__email', 'mobile', 'city')
    readonly_fields = ('created_at',)
    list_select_related = ('user',)
    inlines = [CustomerBookingInline]


# ---------------------------------------------------------------
# Booking flow
# ---------------------------------------------------------------
@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'photographer', 'start_date', 'end_date',
                    'no_of_days', 'status', 'created_at')
    list_filter = ('status', 'start_date', 'photographer')
    search_fields = ('customer__user__full_name', 'customer__user__email',
                     'photographer__user__full_name', 'name', 'email', 'mobile')
    readonly_fields = ('no_of_days', 'created_at', 'updated_at')
    date_hierarchy = 'start_date'
    list_select_related = ('customer__user', 'photographer__user')
    actions = ['mark_accepted', 'mark_rejected', 'mark_completed', 'mark_cancelled']

    # -- helpers --
    def _set_dates_booked(self, booking, booked):
        AvailableDate.objects.filter(
            photographer=booking.photographer,
            date__range=(booking.start_date, booking.end_date),
        ).update(is_booked=booked)

    def _overlaps_accepted(self, booking):
        return Booking.objects.filter(
            photographer=booking.photographer,
            status=Booking.STATUS_ACCEPTED,
            start_date__lte=booking.end_date,
            end_date__gte=booking.start_date,
        ).exclude(pk=booking.pk).exists()

    def _change_status(self, request, queryset, new_status):
        for booking in queryset:
            was_accepted = booking.status == Booking.STATUS_ACCEPTED
            if new_status == Booking.STATUS_ACCEPTED and self._overlaps_accepted(booking):
                self.message_user(
                    request,
                    f"Booking #{booking.id} overlaps another accepted booking for "
                    f"{booking.photographer}. Skipped.",
                    level=messages.WARNING,
                )
                continue
            booking.status = new_status
            booking.save(update_fields=['status', 'updated_at'])
            if new_status == Booking.STATUS_ACCEPTED:
                self._set_dates_booked(booking, True)
            elif was_accepted and new_status in (Booking.STATUS_REJECTED, Booking.STATUS_CANCELLED):
                self._set_dates_booked(booking, False)

    # -- actions --
    @admin.action(description='Mark selected bookings as Accepted')
    def mark_accepted(self, request, queryset):
        self._change_status(request, queryset, Booking.STATUS_ACCEPTED)

    @admin.action(description='Mark selected bookings as Rejected')
    def mark_rejected(self, request, queryset):
        self._change_status(request, queryset, Booking.STATUS_REJECTED)

    @admin.action(description='Mark selected bookings as Completed')
    def mark_completed(self, request, queryset):
        self._change_status(request, queryset, Booking.STATUS_COMPLETED)

    @admin.action(description='Mark selected bookings as Cancelled')
    def mark_cancelled(self, request, queryset):
        self._change_status(request, queryset, Booking.STATUS_CANCELLED)


@admin.register(Enquiry)
class EnquiryAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'photographer', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('customer__user__full_name', 'photographer__user__full_name', 'message')
    readonly_fields = ('created_at',)
    list_select_related = ('customer__user', 'photographer__user')


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('id', 'booking', 'photographer', 'package', 'extra_amt', 'total_amt',
                    'payment_status', 'created_at')
    list_filter = ('payment_status',)
    list_editable = ('payment_status',)
    readonly_fields = ('total_amt', 'created_at', 'updated_at')
    search_fields = ('photographer__user__full_name', 'booking__name')
    list_select_related = ('photographer__user', 'package', 'booking')