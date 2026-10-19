from rest_framework.routers import DefaultRouter

from .views import ControlViewSet

router = DefaultRouter()
router.register("controls", ControlViewSet, basename="control")

urlpatterns = router.urls
