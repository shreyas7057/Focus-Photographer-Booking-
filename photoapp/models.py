from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Category(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Photographer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='photographer_profile')
    location = models.CharField(max_length=100)
    studio_name = models.CharField(max_length=100)
    mobile = models.CharField(max_length=100)
    address = models.CharField(max_length=200)
    cover_photo = models.ImageField(upload_to='cover_photos/', null=True, blank=True)
    your_photo = models.ImageField(upload_to='photographer_self/', blank=True, null=True)

    def __str__(self):
        return self.user.full_name


class Customer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='customer_profile')
    mobile = models.CharField(max_length=15, blank=True)
    address = models.TextField(blank=True)
    profile_photo = models.ImageField(upload_to='customer_photos/', blank=True, null=True)

    def __str__(self):
        return self.user.full_name


class Gallery(models.Model):
    photographer = models.ForeignKey(Photographer, on_delete=models.CASCADE, related_name='gallery_images')
    photo = models.ImageField(upload_to='gallery')

    def __str__(self):
        return self.photographer.user.full_name


class Team(models.Model):
    photographer = models.ForeignKey(Photographer, on_delete=models.CASCADE, related_name='team_members')
    image = models.ImageField(upload_to="team/", blank=True, null=True)
    name = models.CharField(max_length=100)
    speciality = models.CharField(max_length=100)

    def __str__(self):
        return self.photographer.user.full_name


class Stat(models.Model):
    photographer = models.ForeignKey(Photographer, on_delete=models.CASCADE, related_name='stats')
    projects = models.IntegerField()
    customers = models.IntegerField()
    albums = models.IntegerField()
    completed = models.IntegerField()

    def __str__(self):
        return self.photographer.user.full_name


class Service(models.Model):
    photographer = models.ForeignKey(Photographer, on_delete=models.CASCADE, related_name='services')
    serviceType = models.CharField(max_length=100)
    description = models.TextField()

    def __str__(self):
        return self.photographer.user.full_name


class Package(models.Model):
    photographer = models.ForeignKey(Photographer, on_delete=models.CASCADE, related_name='packages')
    name = models.CharField(max_length=100)
    description = models.TextField()
    price = models.IntegerField()

    def __str__(self):
        return self.photographer.user.full_name


class Booking(models.Model):

    STATUS_REQUESTED = 'Requested'
    STATUS_ACCEPTED = 'Accepted'
    STATUS_REJECTED = 'Rejected'
    STATUS_COMPLETED = 'Completed'

    BOOKING_STATUS = (
        (STATUS_REQUESTED, 'Requested'),
        (STATUS_ACCEPTED, 'Accepted'),
        (STATUS_REJECTED, 'Rejected'),
        (STATUS_COMPLETED, 'Completed'),
    )

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='bookings')
    photographer = models.ForeignKey(Photographer, on_delete=models.CASCADE, related_name='bookings')
    name = models.CharField(max_length=200)
    email = models.EmailField()
    mobile = models.CharField(max_length=10)
    start_date = models.DateField()
    end_date = models.DateField()
    address = models.TextField()
    no_of_days = models.IntegerField(null=True, blank=True)
    comment = models.TextField()
    status = models.CharField(max_length=20, choices=BOOKING_STATUS, default=STATUS_REQUESTED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.id)

    def save(self, *args, **kwargs):
        if self.start_date and self.end_date:
            self.no_of_days = abs((self.end_date - self.start_date).days)
        return super().save(*args, **kwargs)


class Invoice(models.Model):
    photographer = models.ForeignKey(Photographer, on_delete=models.CASCADE, related_name='invoices')
    package = models.ForeignKey(Package, on_delete=models.CASCADE)
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='invoice')
    extra_amt = models.IntegerField(null=True, blank=True, default=0)
    total_amt = models.IntegerField(null=True, blank=True)
    payment_status = models.CharField(max_length=100)
    created_at = models.DateField(auto_now_add=True)
    updated_at = models.DateField(auto_now=True)

    def __str__(self):
        return self.photographer.user.full_name

    def calc_total_amt(self):
        self.total_amt = self.package.price + (self.extra_amt or 0)
        return self.total_amt