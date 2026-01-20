from rest_framework.throttling import UserRateThrottle

class KitCreationThrottle(UserRateThrottle):
    def allow_request(self, request, view):
        # Allow all GET requests without throttling
        if request.method == "GET":
            return True
        
        # If it's a POST (creation), check limits
        return super().allow_request(request, view)
    
    def get_scope(self, request, view):
        user = request.user

        if user.is_authenticated and hasattr(user, 'profile') and user.profile.is_pro:
            return 'kits-create-pro'
        
        return 'kits-create'