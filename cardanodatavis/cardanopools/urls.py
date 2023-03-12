from cardanopools.views import index
from django.urls import path
from . import views

# Wire up our API using automatic URL routing.
# Additionally, we include login URLs for the browsable API.
urlpatterns = [
    path('', views.index, name="index"),
    path('pool/<str:pool_hash>/', views.pool, name='pool'),
    path('stake/<str:stake_hash>/', views.stake, name='stake'),
    path('live-leverage', views.liveleverage, name='liveleverage'),
    path('leverageperepoch', views.leverageperepoch, name='leverageperepoch'),
    path('attack51', views.attack51, name='attack51'),
    path('richestlist', views.richestlist, name='richestlist'),
    path('epochstatistics', views.epochstatistics, name='epochstatistics'),
]