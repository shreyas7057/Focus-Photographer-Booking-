from django.urls import path
from . import views

urlpatterns = [
    path('register/customer/', views.register_customer, name='register-customer'),
    path('register/photographer/', views.register_photographer, name='register-photographer'),
    path('login/', views.login_user, name='login-user'),
    path('logout/', views.logout_user, name='logout-user'),

]