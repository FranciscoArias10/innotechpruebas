# -*- coding: utf-8 -*-
from rest_framework import status
from rest_framework.test import APITestCase

from app.models import VersionAppMovil

class AppVersionTests(APITestCase):

    def setUp(self):
        # Aseguramos que haya un registro para iOS
        VersionAppMovil.objects.create(
            plataforma=VersionAppMovil.IOS,
            version_minima='1.0.0',
            version_actual='1.5.0',
            forzar_actualizacion=True
        )
        self.url = '/api/v1.0.0/movil/app/version/'

    def test_get_version_default_android_no_auth(self):
        """
        Prueba que se puede obtener la versión de android por defecto,
        sin estar autenticado, y que si no existe en BD retorna el fallback.
        """
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        body = response.json()
        self.assertTrue(body['isSuccess'])
        self.assertIn('data', body)
        
        data = body['data']
        self.assertEqual(data['plataforma'], 'android')
        self.assertEqual(data['version_minima'], '1.0.0')
        self.assertEqual(data['version_actual'], '1.0.0')
        self.assertFalse(data['forzar_actualizacion'])

    def test_get_version_ios_existing_no_auth(self):
        """
        Prueba que si especificamos plataforma=ios y existe en BD,
        trae la información correcta.
        """
        response = self.client.get(self.url + '?plataforma=ios')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        body = response.json()
        self.assertTrue(body['isSuccess'])
        
        data = body['data']
        self.assertEqual(data['plataforma'], 'ios')
        self.assertEqual(data['version_minima'], '1.0.0')
        self.assertEqual(data['version_actual'], '1.5.0')
        self.assertTrue(data['forzar_actualizacion'])

    def test_get_version_invalid_platform(self):
        """
        Prueba que si se manda una plataforma inválida, retorna 400.
        """
        response = self.client.get(self.url + '?plataforma=windows')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        body = response.json()
        self.assertFalse(body['isSuccess'])
        self.assertEqual(body['message'], 'Plataforma inválida. Use "android" o "ios".')
