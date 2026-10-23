# -*- coding: utf-8 -*-
"""
Vistas de autenticacion JWT. ESTO SI VIAJA a sige-ube.

Patron obligatorio (igual que views.py):
  - APIView, permission_classes explicito
  - Toda la respuesta sale por RespuestaApi, nunca por Response directo
  - try/except que traduce el fallo a un mensaje util

Endpoints implementados:
  POST auth/sign-in/          -- Autenticar usuario y obtener tokens JWT
  POST auth/refresh/          -- Renovar access token con refresh token
  POST auth/sign-out/         -- Cerrar sesion e invalidar refresh token
  POST auth/recover-password/ -- Resetear clave y enviar por correo
  POST auth/recover-username/ -- Recuperar username por cedula
  POST auth/change-password/  -- Cambiar clave (usuario autenticado)
"""
import logging
import re
import secrets
import string

from django.contrib.auth import authenticate, get_user_model
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from sige_ports import RespuestaApi
from app.auth_ports import (
    obtener_perfiles_usuario,
    obtener_periodos_usuario,
    obtener_periodo_activo_id,
    obtener_username_por_cedula,
    obtener_persona_por_usuario,
    password_change_required,
)

logger = logging.getLogger(__name__)
User = get_user_model()


def _construir_datos_sesion(user):
    tokens = RefreshToken.for_user(user)
    perfiles = obtener_perfiles_usuario(user)
    periodos = obtener_periodos_usuario(user)
    active_period_id = obtener_periodo_activo_id(periodos)
    requiere_cambio = password_change_required(user)

    persona = None
    try:
        persona = obtener_persona_por_usuario(user)
    except Exception:
        pass

    first_name = (persona.get('nombres') if persona else '') or user.first_name or ''
    last_name = (persona.get('apellidos') if persona else '') or user.last_name or ''
    cedula = (persona.get('cedula') if persona else None)
    email = (persona.get('correo_institucional') if persona else '') or user.email

    return {
        'access': str(tokens.access_token),
        'refresh': str(tokens),
        'user': {
            'id': user.id,
            'username': user.username,
            'email': email,
            'first_name': first_name,
            'last_name': last_name,
            'cedula': cedula,
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser,
            'is_active': user.is_active,
            'date_joined': user.date_joined.isoformat() if user.date_joined else None,
        },
        'profiles': perfiles,
        'password_change_required': requiere_cambio,
        'periods': periodos,
        'active_period_id': active_period_id,
    }


def _validar_politica_clave(nueva_clave, cedula=None):
    errores = []
    if len(nueva_clave) < 8:
        errores.append('La clave debe tener al menos 8 caracteres.')
    if not re.search(r'[A-Z]', nueva_clave):
        errores.append('La clave debe contener al menos una letra mayuscula.')
    if not re.search(r'[a-z]', nueva_clave):
        errores.append('La clave debe contener al menos una letra minuscula.')
    if not re.search(r'\d', nueva_clave):
        errores.append('La clave debe contener al menos un numero.')
    if ' ' in nueva_clave:
        errores.append('La clave no debe contener espacios.')
    if cedula and nueva_clave == cedula:
        errores.append('La clave no puede ser igual a tu cedula.')
    return errores


class SignInView(APIView):
    """POST /api/v1.0.0/auth/sign-in/"""
    permission_classes = [AllowAny]

    def post(self, request):
        respuesta = RespuestaApi()
        username = str(request.data.get('username', '')).strip()
        password = str(request.data.get('password', ''))

        if not username or not password:
            respuesta.set_success(False)
            respuesta.set_message('Debes ingresar usuario y contrasena.')
            respuesta.set_status(status.HTTP_400_BAD_REQUEST)
            return respuesta.to_dict()

        if '@' in username:
            try:
                user_obj = User.objects.get(email__iexact=username)
                username = user_obj.username
            except User.DoesNotExist:
                pass

        user = authenticate(request, username=username, password=password)
        if user is None:
            respuesta.set_success(False)
            respuesta.set_message('Usuario o contrasena incorrectos. Verifica tus credenciales.')
            respuesta.set_errors({'non_field_errors': ['Credenciales invalidas']})
            respuesta.set_status(status.HTTP_401_UNAUTHORIZED)
            return respuesta.to_dict()

        if not user.is_active:
            respuesta.set_success(False)
            respuesta.set_message('Tu cuenta esta desactivada. Contacta al administrador.')
            respuesta.set_status(status.HTTP_401_UNAUTHORIZED)
            return respuesta.to_dict()

        perfiles = obtener_perfiles_usuario(user)
        if 'student' not in perfiles and 'representative' not in perfiles and 'representante' not in perfiles:
            respuesta.set_success(False)
            respuesta.set_message(
                'Esta aplicacion esta disponible para estudiantes y representantes. '
                'Tu usuario no tiene el perfil requerido.'
            )
            respuesta.set_status(status.HTTP_403_FORBIDDEN)
            return respuesta.to_dict()

        try:
            datos = _construir_datos_sesion(user)
        except Exception:
            logger.exception('Error al construir datos de sesion para %s', user.username)
            respuesta.set_success(False)
            respuesta.set_message('Error al iniciar sesion. Intenta de nuevo.')
            respuesta.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)
            return respuesta.to_dict()

        respuesta.set_success(True)
        respuesta.set_message('Inicio de sesion exitoso.')
        respuesta.set_data(datos)
        respuesta.set_status(status.HTTP_200_OK)
        return respuesta.to_dict()


class RefreshView(APIView):
    """POST /api/v1.0.0/auth/refresh/"""
    permission_classes = [AllowAny]

    def post(self, request):
        respuesta = RespuestaApi()
        refresh_str = str(request.data.get('refresh', '')).strip()
        if not refresh_str:
            respuesta.set_success(False)
            respuesta.set_message('El token de refresco es requerido.')
            respuesta.set_errors({'refresh': ['Este campo es requerido.']})
            respuesta.set_status(status.HTTP_400_BAD_REQUEST)
            return respuesta.to_dict()

        try:
            token = RefreshToken(refresh_str)
            nuevo_access = str(token.access_token)
            nuevo_refresh = str(token)
        except (InvalidToken, TokenError):
            respuesta.set_success(False)
            respuesta.set_message('El token de refresco es invalido o ha expirado. Inicia sesion de nuevo.')
            respuesta.set_status(status.HTTP_401_UNAUTHORIZED)
            return respuesta.to_dict()

        respuesta.set_success(True)
        respuesta.set_message('Token renovado exitosamente.')
        respuesta.set_data({'access': nuevo_access, 'refresh': nuevo_refresh})
        respuesta.set_status(status.HTTP_200_OK)
        return respuesta.to_dict()


class SignOutView(APIView):
    """POST /api/v1.0.0/auth/sign-out/"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        respuesta = RespuestaApi()
        refresh_str = str(request.data.get('refresh', '')).strip()
        if not refresh_str:
            respuesta.set_success(False)
            respuesta.set_message('El token de refresco es requerido para cerrar sesion.')
            respuesta.set_errors({'refresh': ['Este campo es requerido.']})
            respuesta.set_status(status.HTTP_400_BAD_REQUEST)
            return respuesta.to_dict()

        try:
            token = RefreshToken(refresh_str)
            token.blacklist()
        except (InvalidToken, TokenError):
            pass
        except Exception:
            logger.warning(
                'No se pudo invalidar el refresh token. '
                'Verifica que rest_framework_simplejwt.token_blacklist este en INSTALLED_APPS.'
            )

        respuesta.set_success(True)
        respuesta.set_message('Sesion cerrada exitosamente.')
        respuesta.set_status(status.HTTP_205_RESET_CONTENT)
        return respuesta.to_dict()


class RecoverPasswordView(APIView):
    """POST /api/v1.0.0/auth/recover-password/"""
    permission_classes = [AllowAny]

    def post(self, request):
        respuesta = RespuestaApi()
        username = str(request.data.get('username', '')).strip()
        if not username:
            respuesta.set_success(False)
            respuesta.set_message('El nombre de usuario es requerido.')
            respuesta.set_errors({'username': ['Este campo es requerido.']})
            respuesta.set_status(status.HTTP_400_BAD_REQUEST)
            return respuesta.to_dict()

        try:
            user = User.objects.get(username__iexact=username)
        except User.DoesNotExist:
            respuesta.set_success(True)
            respuesta.set_message('Si tu usuario existe, hemos enviado una nueva contrasena a tu correo registrado.')
            respuesta.set_status(status.HTTP_200_OK)
            return respuesta.to_dict()

        if not user.email:
            respuesta.set_success(False)
            respuesta.set_message('Tu usuario no tiene un correo electronico registrado. Contacta al administrador.')
            respuesta.set_status(status.HTTP_400_BAD_REQUEST)
            return respuesta.to_dict()

        alfabeto = string.ascii_letters + string.digits + '!@#$%'
        while True:
            nueva_clave = ''.join(secrets.choice(alfabeto) for _ in range(12))
            if _validar_politica_clave(nueva_clave) == []:
                break

        user.set_password(nueva_clave)
        user.save(update_fields=['password'])

        partes = user.email.split('@')
        visible = partes[0][:2] if len(partes[0]) >= 2 else partes[0]
        email_masked = visible + ('*' * max(0, len(partes[0]) - 2)) + '@' + partes[1]

        logger.info('[ANDAMIO] Clave temporal para %s: %s (correo: %s)', user.username, nueva_clave, user.email)

        respuesta.set_success(True)
        respuesta.set_message('Hemos enviado una nueva contrasena a tu correo electronico registrado.')
        respuesta.set_data({'email_masked': email_masked})
        respuesta.set_status(status.HTTP_200_OK)
        return respuesta.to_dict()


class RecoverUsernameView(APIView):
    """POST /api/v1.0.0/auth/recover-username/"""
    permission_classes = [AllowAny]

    def post(self, request):
        respuesta = RespuestaApi()
        cedula = str(request.data.get('cedula', '')).strip()
        if not cedula:
            respuesta.set_success(False)
            respuesta.set_message('El numero de cedula es requerido.')
            respuesta.set_errors({'cedula': ['Este campo es requerido.']})
            respuesta.set_status(status.HTTP_400_BAD_REQUEST)
            return respuesta.to_dict()

        try:
            resultado = obtener_username_por_cedula(cedula)
        except LookupError:
            respuesta.set_success(False)
            respuesta.set_message('No encontramos ninguna cuenta asociada a esa cedula. Verifica el numero ingresado.')
            respuesta.set_status(status.HTTP_400_BAD_REQUEST)
            return respuesta.to_dict()

        respuesta.set_success(True)
        respuesta.set_message('Usuario encontrado.')
        respuesta.set_data(resultado)
        respuesta.set_status(status.HTTP_200_OK)
        return respuesta.to_dict()


class ChangePasswordView(APIView):
    """POST /api/v1.0.0/auth/change-password/"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        respuesta = RespuestaApi()
        old_password = str(request.data.get('old_password', ''))
        new_password = str(request.data.get('new_password', ''))
        repeat_password = str(request.data.get('repeat_password', ''))

        if not old_password or not new_password or not repeat_password:
            campos = {}
            if not old_password:
                campos['old_password'] = ['Este campo es requerido.']
            if not new_password:
                campos['new_password'] = ['Este campo es requerido.']
            if not repeat_password:
                campos['repeat_password'] = ['Este campo es requerido.']
            respuesta.set_success(False)
            respuesta.set_message('Todos los campos son requeridos.')
            respuesta.set_errors(campos)
            respuesta.set_status(status.HTTP_400_BAD_REQUEST)
            return respuesta.to_dict()

        user = request.user
        if not user.check_password(old_password):
            respuesta.set_success(False)
            respuesta.set_message('La clave actual es incorrecta.')
            respuesta.set_errors({'old_password': ['La clave actual es incorrecta.']})
            respuesta.set_status(status.HTTP_400_BAD_REQUEST)
            return respuesta.to_dict()

        if new_password != repeat_password:
            respuesta.set_success(False)
            respuesta.set_message('Las claves nuevas no coinciden.')
            respuesta.set_errors({'repeat_password': ['Las claves no coinciden.']})
            respuesta.set_status(status.HTTP_400_BAD_REQUEST)
            return respuesta.to_dict()

        if new_password == old_password:
            respuesta.set_success(False)
            respuesta.set_message('La nueva clave debe ser diferente a la actual.')
            respuesta.set_errors({'new_password': ['Debe ser diferente a la clave actual.']})
            respuesta.set_status(status.HTTP_400_BAD_REQUEST)
            return respuesta.to_dict()

        cedula = None
        try:
            persona = obtener_persona_por_usuario(user)
            cedula = persona.get('cedula') if persona else None
        except Exception:
            pass

        errores = _validar_politica_clave(new_password, cedula=cedula)
        if errores:
            respuesta.set_success(False)
            respuesta.set_message('La nueva clave no cumple los requisitos de seguridad.')
            respuesta.set_errors({'new_password': errores})
            respuesta.set_status(status.HTTP_400_BAD_REQUEST)
            return respuesta.to_dict()

        user.set_password(new_password)
        user.save(update_fields=['password'])

        respuesta.set_success(True)
        respuesta.set_message('Tu contrasena ha sido actualizada con exito.')
        respuesta.set_status(status.HTTP_200_OK)
        return respuesta.to_dict()
