from django.contrib.auth import authenticate, login, logout, get_user_model
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required

User = get_user_model()


def register_customer(request):
    if request.method == "POST":
        email = request.POST.get('email')
        full_name = request.POST.get('full_name')
        password = request.POST.get('password')
        password2 = request.POST.get('password2')

        if not email or not full_name or not password:
            messages.error(request, 'All fields are required.')
            return redirect('register-customer')

        if password != password2:
            messages.error(request, 'Passwords do not match.')
            return redirect('register-customer')

        if User.objects.filter(email=email).exists():
            messages.error(request, 'An account with this email already exists.')
            return redirect('register-customer')

        user = User(
            email=email,
            full_name=full_name,
            user_type=User.CUSTOMER,
            is_active=True,
        )
        user.set_password(password)
        user.save()
        messages.success(request, 'Registered successfully! Please log in.')
        return redirect('login-user')

    return render(request, 'user/register_customer.html')


def register_photographer(request):
    if request.method == "POST":
        email = request.POST.get('email')
        full_name = request.POST.get('full_name')
        password = request.POST.get('password')
        password2 = request.POST.get('password2')

        if not email or not full_name or not password:
            messages.error(request, 'All fields are required.')
            return redirect('register-photographer')

        if password != password2:
            messages.error(request, 'Passwords do not match.')
            return redirect('register-photographer')

        if User.objects.filter(email=email).exists():
            messages.error(request, 'An account with this email already exists.')
            return redirect('register-photographer')

        user = User(
            email=email,
            full_name=full_name,
            user_type=User.PHOTOGRAPHER,
            is_active=True,   # flip to False here if you want admin approval before they can log in
        )
        user.set_password(password)
        user.save()
        messages.success(request, 'Registered successfully! Please log in.')
        return redirect('login-user')

    return render(request, 'user/register_photographer.html')


def login_user(request):
    if request.method == "POST":
        email = request.POST.get('email')
        password = request.POST.get('password')
        user = authenticate(request, email=email, password=password)

        if user is None:
            messages.error(request, 'Email or password is incorrect.')
            return redirect('login-user')

        login(request, user)
        messages.success(request, 'Logged in successfully!')

        if user.user_type == User.ADMIN:
            return redirect('custom_admin_index')
        elif user.user_type == User.PHOTOGRAPHER:
            return redirect('custom_photographer_index')
        else:
            return redirect('custom_customer_index')

    return render(request, 'user/login.html')


@login_required(login_url='login-user')
def logout_user(request):
    logout(request)
    messages.error(request, 'Logged out successfully!')
    return redirect('login-user')