from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from .models import Cliente

def register_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        nombre = request.POST['nombre']
        identificador = request.POST['identificador']

        user = User.objects.create_user(username=username, password=password)
        Cliente.objects.create(
            user=user,
            nombre=nombre,
            identificador_externo=identificador
        )
        return redirect('login')

    return render(request, 'reservas/registro.html')


def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('lista_recursos_usuario')  # vista que lista recursos
        else:
            return render(request, 'reservas/login.html', {'error': 'Credenciales inválidas'})

    return render(request, 'reservas/login.html')


def logout_view(request):
    logout(request)
    return redirect('login')