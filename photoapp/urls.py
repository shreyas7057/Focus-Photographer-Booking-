from . import admin_views
from django.urls import path


urlpatterns = [
    path('panel/', admin_views.custom_admin_index, name='custom_admin_index'),

    path('panel/photographers/', admin_views.admin_photographers, name='admin-photographers'),
    path('panel/photographers/<int:pk>/', admin_views.admin_photographer_detail, name='admin-photographer-detail'),
    path('panel/photographers/<int:pk>/toggle/', admin_views.admin_photographer_toggle, name='admin-photographer-toggle'),
    path('panel/photographers/<int:pk>/delete/', admin_views.admin_photographer_delete, name='admin-photographer-delete'),

    path('panel/customers/', admin_views.admin_customers, name='admin-customers'),
    path('panel/customers/<int:pk>/', admin_views.admin_customer_detail, name='admin-customer-detail'),
    path('panel/customers/<int:pk>/toggle/', admin_views.admin_customer_toggle, name='admin-customer-toggle'),
    path('panel/customers/<int:pk>/delete/', admin_views.admin_customer_delete, name='admin-customer-delete'),

    path('panel/bookings/', admin_views.admin_bookings, name='admin-bookings'),
    path('panel/bookings/<int:pk>/', admin_views.admin_booking_detail, name='admin-booking-detail'),
    path('panel/bookings/<int:pk>/status/', admin_views.admin_booking_status, name='admin-booking-status'),

    path('panel/enquiries/', admin_views.admin_enquiries, name='admin-enquiries'),

    path('panel/categories/', admin_views.admin_categories, name='admin-categories'),
    path('panel/categories/add/', admin_views.admin_category_add, name='admin-category-add'),
    path('panel/categories/<int:pk>/edit/', admin_views.admin_category_edit, name='admin-category-edit'),
    path('panel/categories/<int:pk>/delete/', admin_views.admin_category_delete, name='admin-category-delete'),
]