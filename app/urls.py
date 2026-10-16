# -*- coding: utf-8 -*-
"""
Rutas de la app. ESTO SI VIAJA a sige-ube.

Solo rutas relativas: el prefijo (/api/v1.0.0/movil/) lo pone quien incluye
este archivo. Aqui lo pone proyecto/urls.py; alla, api/v1_0_0/urls.py.
"""
from django.urls import path

from app.views import (
    DeviceRegisterView,
    AppVersionView,
    NotificationPreferencesView,
    FeedbackView,
    RepresentativeStudentGradesView,
    RepresentativeStudentAttendanceView,
    RepresentativeStudentScheduleView,
    RepresentativeStudentSummaryView,
)
from app.student_views import (
    StudentSummaryView,
    StudentSubjectsView,
    StudentGradesView,
    StudentSubjectGradesDetailView,
    StudentAttendanceView,
    StudentAttendanceLessonsView,
    StudentJustificationView,
    StudentScheduleView,
    StudentHomeView,
    StudentPlanningView,
    StudentClassmatesView,
    StudentResourceOpenView,
    StudentActivityDetailView,
    StudentCalendarView,
    StudentNoticesView,
    StudentNoticeDetailView,
    StudentNoticeMarkReadView,
    StudentNoticeMarkAllReadView,
    StudentNoticeUnreadCountView,
    StudentTestPushView,
)

urlpatterns = [
    # Dispositivos, version, preferencias y feedback
    path('device/register/', DeviceRegisterView.as_view(), name='movil-device-register'),
    path('app/version/', AppVersionView.as_view(), name='movil-app-version'),
    path('notifications/preferences/', NotificationPreferencesView.as_view(), name='movil-notification-preferences'),
    path('feedback/', FeedbackView.as_view(), name='movil-feedback'),

    # Endpoints del estudiante (Fase 1)
    path('student/home/', StudentHomeView.as_view(), name='movil-student-home'),
    path('student/summary/', StudentSummaryView.as_view(), name='movil-student-summary'),
    path('student/subjects/', StudentSubjectsView.as_view(), name='movil-student-subjects'),
    path('student/grades/', StudentGradesView.as_view(), name='movil-student-grades'),
    path('student/subjects/<int:materia_asignada_id>/grades/', StudentSubjectGradesDetailView.as_view(), name='movil-student-subject-grades-detail'),
    path('student/attendance/', StudentAttendanceView.as_view(), name='movil-student-attendance'),
    path('student/attendance/report/', StudentAttendanceView.as_view(), name='movil-student-attendance-report'),
    path('student/attendance/lessons/', StudentAttendanceLessonsView.as_view(), name='movil-student-attendance-lessons'),
    path('student/attendance/justifications/', StudentJustificationView.as_view(), name='movil-student-attendance-justifications'),
    path('student/attendance/justify/', StudentJustificationView.as_view(), name='movil-student-attendance-justify'),
    path('chat-ia/widget/justificar/', StudentJustificationView.as_view(), name='movil-chatia-justificar'),
    path('student/schedule/', StudentScheduleView.as_view(), name='movil-student-schedule'),
    path('student/subjects/<int:materia_asignada_id>/planning/', StudentPlanningView.as_view(), name='movil-student-subject-planning'),
    path('student/subjects/<int:materia_asignada_id>/classmates/', StudentClassmatesView.as_view(), name='movil-student-subject-classmates'),
    path('student/subjects/<int:materia_asignada_id>/resource-open/', StudentResourceOpenView.as_view(), name='movil-student-resource-open'),
    # Alias sin sufijo movil o con compatibilidad
    path('student/resources/open/', StudentResourceOpenView.as_view(), name='movil-student-resource-open-global'),



    # Tarea 05: Actividades, entregas y calendario
    path('student/activity/<int:actividad_id>/', StudentActivityDetailView.as_view(), name='movil-student-activity-detail'),
    path('student/calendar/', StudentCalendarView.as_view(), name='movil-student-calendar'),
    path('student/activities/pending/', StudentCalendarView.as_view(), name='movil-student-activities-pending'),

    # Tarea 09: Avisos, comunicados y notificaciones
    path('student/notices/', StudentNoticesView.as_view(), name='movil-student-notices'),
    path('student/notices/<int:correo_id>/', StudentNoticeDetailView.as_view(), name='movil-student-notice-detail'),
    path('student/notices/<int:correo_id>/read/', StudentNoticeMarkReadView.as_view(), name='movil-student-notice-read'),
    path('student/notices/mark-all-read/', StudentNoticeMarkAllReadView.as_view(), name='movil-student-notice-mark-all-read'),
    path('student/notices/unread-count/', StudentNoticeUnreadCountView.as_view(), name='movil-student-notice-unread-count'),
    path('student/notices/test-push/', StudentTestPushView.as_view(), name='movil-student-notice-test-push'),
    path('avisos-mensajeria/', StudentNoticeUnreadCountView.as_view(), name='movil-avisos-mensajeria'),

    # Endpoints del representante
    path('representative/students/<int:student_id>/grades/', RepresentativeStudentGradesView.as_view(), name='movil-representative-student-grades'),
    path('representative/students/<int:student_id>/attendance/', RepresentativeStudentAttendanceView.as_view(), name='movil-representative-student-attendance'),
    path('representative/students/<int:student_id>/schedule/', RepresentativeStudentScheduleView.as_view(), name='movil-representative-student-schedule'),
    path('representative/students/<int:student_id>/summary/', RepresentativeStudentSummaryView.as_view(), name='movil-representative-student-summary'),
]