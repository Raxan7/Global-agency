from django.urls import path
from . import views
from . import test_views

app_name = 'global_agency'

urlpatterns = [
    path('test-language/', test_views.test_language_view, name='test_language'),  # Debug view
    path('', views.home, name='home'),
    path('updates/', views.updates_list, name='updates'),
    path('updates/<slug:slug>/', views.update_detail, name='update_detail'),
    path('terms-and-conditions/', views.terms_and_conditions, name='terms_and_conditions'),
    path('privacy-policy/', views.privacy_policy, name='privacy_policy'),
    path('set-language/<str:language>/', views.set_language_view, name='set_language'),  # Language switcher
    path('register/', views.register, name='register'),
    path('contact/', views.contact, name='contact'),
    path('start-application/', views.start_application, name='start_application'),
    path('application-success/', views.application_success, name='application_success'),  # ADD THIS LINE
    path('vyuo-vya-ndani/', views.vyuo_ndani, name='vyuo_ndani'),
    path('university/<str:university_name>/', views.university_detail, name='university_detail'),
    path('universities/country/<str:country>/', views.country_universities, name='country_universities'),
    path('universities/abroad/<str:university_slug>/', views.abroad_university_detail, name='abroad_university_detail'),
    path('universities/countries/', views.all_countries, name='all_countries'),
    path('tcu-services/', views.tcu_services, name='tcu_services'),
]
