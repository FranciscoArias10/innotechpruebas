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
    StudentChatContactsView,
    StudentChatConversationsView,
    StudentChatConversationDetailView,
    StudentChatMessagesView,
    StudentChatReadView,
    StudentChatTypingView,
    StudentQuizDetailView,
    StudentQuizAttemptQuestionsView,
    StudentQuizAttemptReviewView,
    StudentRubrosView,
    StudentRubroDetailView,
    StudentSubirComprobanteView,
    StudentProfileView,
    StudentCarnetView,
    StudentSubjectForumsView,
    StudentForumDetailView,
    StudentForumPostCreateView,
    StudentForumPostActionView,
    StudentSubjectInquiriesView,
    StudentServiceTypesView,
    StudentServiceRequestsView,
    StudentServiceRequestDetailView,
    StudentDocumentsView,
    StudentDocumentUploadView,
)

urlpatterns = [
    # Dispositivos, version, preferencias y feedback
    path('device/register/', DeviceRegisterView.as_view(), name='movil-device-register'),
    path('app/version/', AppVersionView.as_view(), name='movil-app-version'),
    path('notifications/preferences/', NotificationPreferencesView.as_view(), name='movil-notification-preferences'),
    path('feedback/', FeedbackView.as_view(), name='movil-feedback'),

    # Endpoints del estudiante (Fase 1)
    path('student/profile/', StudentProfileView.as_view(), name='movil-student-profile'),
    path('student/carnet/', StudentCarnetView.as_view(), name='movil-student-carnet'),
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

    # Tarea 10: Chat con docentes y compañeros
    path('chat/contacts/', StudentChatContactsView.as_view(), name='movil-chat-contacts'),
    path('chat/conversations/', StudentChatConversationsView.as_view(), name='movil-chat-conversations'),
    path('chat/conversations/create/', StudentChatConversationsView.as_view(), name='movil-chat-conversations-create'),
    path('chat/conversations/<int:conversation_id>/', StudentChatConversationDetailView.as_view(), name='movil-chat-conversation-detail'),
    path('chat/conversations/<int:conversation_id>/messages/', StudentChatMessagesView.as_view(), name='movil-chat-conversation-messages'),
    path('chat/conversations/<int:conversation_id>/read/', StudentChatReadView.as_view(), name='movil-chat-conversation-read'),
    path('chat/conversations/<int:conversation_id>/typing/', StudentChatTypingView.as_view(), name='movil-chat-conversation-typing'),

    # Tarea 11: Cuestionarios y evaluaciones en linea
    path('student/quizzes/<int:cuestionario_id>/', StudentQuizDetailView.as_view(), name='movil-student-quiz-detail'),
    path('student/quizzes/<int:cuestionario_id>/start/', StudentQuizDetailView.as_view(), name='movil-student-quiz-start'),
    path('student/quizzes/attempts/<int:intento_id>/questions/', StudentQuizAttemptQuestionsView.as_view(), name='movil-student-quiz-attempt-questions'),
    path('student/quizzes/attempts/<int:intento_id>/save-answer/', StudentQuizAttemptQuestionsView.as_view(), name='movil-student-quiz-attempt-save-answer'),
    path('student/quizzes/attempts/<int:intento_id>/finish/', StudentQuizAttemptQuestionsView.as_view(), name='movil-student-quiz-attempt-finish'),
    path('student/quizzes/attempts/<int:intento_id>/review/', StudentQuizAttemptReviewView.as_view(), name='movil-student-quiz-attempt-review'),

    # Tarea 12: Foros y consultas al docente
    path('student/subjects/<int:materia_asignada_id>/forums/', StudentSubjectForumsView.as_view(), name='movil-student-subject-forums'),
    path('student/forums/<int:foro_id>/', StudentForumDetailView.as_view(), name='movil-student-forum-detail'),
    path('student/forums/<int:foro_id>/posts/', StudentForumPostCreateView.as_view(), name='movil-student-forum-post-create'),
    path('student/forums/posts/<int:post_id>/', StudentForumPostActionView.as_view(), name='movil-student-forum-post-action'),
    path('student/subjects/<int:materia_asignada_id>/inquiries/', StudentSubjectInquiriesView.as_view(), name='movil-student-subject-inquiries'),

    # Tarea 15: Pensiones, rubros y comprobantes de pago
    path('student/finance/rubros/', StudentRubrosView.as_view(), name='movil-student-rubros'),
    path('student/finance/rubros/<int:rubro_id>/', StudentRubroDetailView.as_view(), name='movil-student-rubro-detail'),
    path('student/finance/comprobante/', StudentSubirComprobanteView.as_view(), name='movil-student-subir-comprobante'),
    path('student/pensions/', StudentRubrosView.as_view(), name='movil-student-pensions'),

    # Tarea 16: Balcón de servicios y trámites estudiantiles
    path('student/services/types/', StudentServiceTypesView.as_view(), name='movil-student-service-types'),
    path('student/services/requests/', StudentServiceRequestsView.as_view(), name='movil-student-service-requests'),
    path('student/services/requests/<int:solicitud_id>/', StudentServiceRequestDetailView.as_view(), name='movil-student-service-request-detail'),
    path('student/documents/', StudentDocumentsView.as_view(), name='movil-student-documents'),
    path('student/documents/upload/', StudentDocumentUploadView.as_view(), name='movil-student-document-upload'),

    # Endpoints del representante
    path('representative/students/<int:student_id>/grades/', RepresentativeStudentGradesView.as_view(), name='movil-representative-student-grades'),
    path('representative/students/<int:student_id>/attendance/', RepresentativeStudentAttendanceView.as_view(), name='movil-representative-student-attendance'),
    path('representative/students/<int:student_id>/schedule/', RepresentativeStudentScheduleView.as_view(), name='movil-representative-student-schedule'),
    path('representative/students/<int:student_id>/summary/', RepresentativeStudentSummaryView.as_view(), name='movil-representative-student-summary'),
]