from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
    def create_user(self, email, full_name, password=None, **extra_fields):
        if not email:
            raise ValueError("You must provide an email address")

        email = self.normalize_email(email)
        user = self.model(email=email, full_name=full_name, **extra_fields)

        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, email, password, full_name, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('user_type', User.ADMIN)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True')

        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True')

        return self.create_user(email, full_name, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    ADMIN = 1
    PHOTOGRAPHER = 2
    CUSTOMER = 3

    USER_TYPE = (
        (ADMIN, 'Admin'),
        (PHOTOGRAPHER, 'Photographer'),
        (CUSTOMER, 'Customer'),
    )

    user_type = models.PositiveSmallIntegerField(choices=USER_TYPE, default=CUSTOMER)
    email = models.EmailField(_("Email Id"), unique=True)
    full_name = models.CharField(_("Full Name"), max_length=255)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name']

    def __str__(self):
        return self.email

    @property
    def is_admin_user(self):
        return self.user_type == self.ADMIN

    @property
    def is_photographer_user(self):
        return self.user_type == self.PHOTOGRAPHER

    @property
    def is_customer_user(self):
        return self.user_type == self.CUSTOMER