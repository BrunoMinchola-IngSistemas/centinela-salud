from rest_framework.routers import DefaultRouter

from .views import RemediationPlanViewSet

router = DefaultRouter()
router.register("remediation-plans", RemediationPlanViewSet, basename="remediation-plan")

urlpatterns = router.urls
