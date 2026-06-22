from django.contrib import admin
from django.urls import path, include
from apis import urls
urlpatterns = [
    path('admin/', admin.site.urls),
    path('api-auth/', include('rest_framework.urls')),
    path('silk/', include('silk.urls'), name='silk'),
    path('', include('apis.urls'))
]
