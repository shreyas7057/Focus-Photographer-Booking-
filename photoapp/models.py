from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models

phone_validator = RegexValidator(r'^\d{10}$', 'Enter a 10-digit mobile number.')


# ---------------------------------------------------------------
# Shared
# ---------------------------------------------------------------
class Category(models.Model):
    """Shoot type: Wedding, Portrait, Event, Product, etc."""
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['name']

    def __str__(self):
        return self.name


# ---------------------------------------------------------------
# Photographer side
# ---------------------------------------------------------------
class Photographer(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name='photographer_profile')
    studio_name = models.CharField(max_length=100)
    location = models.CharField(max_length=100, db_index=True)   # city/area used by the search
    address = models.CharField(max_length=200)
    mobile = models.CharField(max_length=10, validators=[phone_validator])
    bio = models.TextField(blank=True)
    experience_years = models.PositiveSmallIntegerField(default=0)
    categories = models.ManyToManyField(Category, blank=True, related_name='photographers')
    cover_photo = models.ImageField(upload_to='cover_photos/', null=True, blank=True)
    your_photo = models.ImageField(upload_to='photographer_self/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.full_name} ({self.studio_name})"


class Album(models.Model):
    """A group of photos from one shoot, shown on the portfolio page."""
    photographer = models.ForeignKey(Photographer, on_delete=models.CASCADE, related_name='albums')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='albums')
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.photographer.user.full_name}"


class Gallery(models.Model):
    """Portfolio photo. Can belong to an album or stand alone."""
    photographer = models.ForeignKey(Photographer, on_delete=models.CASCADE, related_name='gallery_images')
    album = models.ForeignKey(Album, on_delete=models.SET_NULL, null=True, blank=True,
                              related_name='photos')
    photo = models.ImageField(upload_to='gallery/')
    caption = models.CharField(max_length=200, blank=True)
    is_featured = models.BooleanField(default=False)   # show first on the profile page
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Gallery'
        ordering = ['-is_featured', '-uploaded_at']

    def __str__(self):
        return f"Photo by {self.photographer.user.full_name}"


class Team(models.Model):
    photographer = models.ForeignKey(Photographer, on_delete=models.CASCADE, related_name='team_members')
    image = models.ImageField(upload_to='team/', null=True, blank=True)
    name = models.CharField(max_length=100)
    speciality = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.name} ({self.photographer.studio_name})"


class Stat(models.Model):
    photographer = models.OneToOneField(Photographer, on_delete=models.CASCADE, related_name='stats')
    projects = models.PositiveIntegerField(default=0)
    customers = models.PositiveIntegerField(default=0)
    albums = models.PositiveIntegerField(default=0)
    completed = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"Stats - {self.photographer.user.full_name}"


class Service(models.Model):
    photographer = models.ForeignKey(Photographer, on_delete=models.CASCADE, related_name='services')
    serviceType = models.CharField(max_length=100)
    description = models.TextField()

    def __str__(self):
        return f"{self.serviceType} - {self.photographer.user.full_name}"


class Package(models.Model):
    photographer = models.ForeignKey(Photographer, on_delete=models.CASCADE, related_name='packages')
    name = models.CharField(max_length=100)
    description = models.TextField()
    price = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.name} - {self.photographer.user.full_name}"


class AvailableDate(models.Model):
    """Dates the photographer marks as open for work (their calendar)."""
    photographer = models.ForeignKey(Photographer, on_delete=models.CASCADE,
                                     related_name='available_dates')
    date = models.DateField()
    is_booked = models.BooleanField(default=False)

    class Meta:
        unique_together = ('photographer', 'date')
        ordering = ['date']

    def __str__(self):
        return f"{self.photographer.user.full_name} - {self.date}"


# ---------------------------------------------------------------
# Customer side
# ---------------------------------------------------------------
class Customer(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name='customer_profile')
    mobile = models.CharField(max_length=10, blank=True, validators=[phone_validator])
    city = models.CharField(max_length=100, blank=True)
    address = models.TextField(blank=True)
    profile_photo = models.ImageField(upload_to='customer_photos/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.full_name

    @property
    def total_bookings(self):
        return self.bookings.count()


# ---------------------------------------------------------------
# Booking flow
# ---------------------------------------------------------------
class Booking(models.Model):
    STATUS_REQUESTED = 'Requested'
    STATUS_ACCEPTED = 'Accepted'
    STATUS_REJECTED = 'Rejected'
    STATUS_COMPLETED = 'Completed'
    STATUS_CANCELLED = 'Cancelled'

    BOOKING_STATUS = (
        (STATUS_REQUESTED, 'Requested'),   # customer sent the request, waiting for photographer
        (STATUS_ACCEPTED, 'Accepted'),     # photographer confirmed
        (STATUS_REJECTED, 'Rejected'),     # photographer declined
        (STATUS_COMPLETED, 'Completed'),   # shoot is done
        (STATUS_CANCELLED, 'Cancelled'),   # customer withdrew the request
    )

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='bookings')
    photographer = models.ForeignKey(Photographer, on_delete=models.CASCADE, related_name='bookings')
    package = models.ForeignKey(Package, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='bookings')

    # Contact details for this shoot (pre-fill from the customer's profile in the form)
    name = models.CharField(max_length=200)
    email = models.EmailField()
    mobile = models.CharField(max_length=10, validators=[phone_validator])

    start_date = models.DateField()
    end_date = models.DateField()
    no_of_days = models.PositiveIntegerField(null=True, blank=True)
    address = models.TextField()          # where the shoot will take place
    comment = models.TextField(blank=True)

    status = models.CharField(max_length=20, choices=BOOKING_STATUS, default=STATUS_REQUESTED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Booking #{self.id} - {self.customer} with {self.photographer.user.full_name}"

    def clean(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({'end_date': 'End date cannot be before the start date.'})

    def save(self, *args, **kwargs):
        if self.start_date and self.end_date:
            # inclusive: a one-day shoot counts as 1 day
            self.no_of_days = (self.end_date - self.start_date).days + 1
        super().save(*args, **kwargs)


class Enquiry(models.Model):
    """A question to a photographer that does not lock any dates."""
    STATUS_OPEN = 'Open'
    STATUS_RESPONDED = 'Responded'
    STATUS_CLOSED = 'Closed'

    ENQUIRY_STATUS = (
        (STATUS_OPEN, 'Open'),
        (STATUS_RESPONDED, 'Responded'),
        (STATUS_CLOSED, 'Closed'),
    )

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='enquiries')
    photographer = models.ForeignKey(Photographer, on_delete=models.CASCADE, related_name='enquiries')
    message = models.TextField()
    mobile = models.CharField(max_length=10, blank=True, validators=[phone_validator])
    reply = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=ENQUIRY_STATUS, default=STATUS_OPEN)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Enquiries'
        ordering = ['-created_at']

    def __str__(self):
        return f"Enquiry #{self.id} - {self.customer} to {self.photographer.user.full_name}"


class Invoice(models.Model):
    PAYMENT_STATUS = (
        ('Pending', 'Pending'),
        ('Paid', 'Paid'),
    )

    photographer = models.ForeignKey(Photographer, on_delete=models.CASCADE, related_name='invoices')
    package = models.ForeignKey(Package, on_delete=models.CASCADE, related_name='invoices')
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='invoice')
    extra_amt = models.PositiveIntegerField(default=0)
    total_amt = models.PositiveIntegerField(null=True, blank=True)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='Pending')
    created_at = models.DateField(auto_now_add=True)
    updated_at = models.DateField(auto_now=True)

    def __str__(self):
        return f"Invoice for booking #{self.booking_id}"

    def calc_total_amt(self):
        self.total_amt = self.package.price + (self.extra_amt or 0)
        return self.total_amt

    def save(self, *args, **kwargs):
        self.calc_total_amt()
        super().save(*args, **kwargs)