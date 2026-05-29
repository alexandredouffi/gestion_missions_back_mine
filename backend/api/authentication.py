from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken


class JWTQueryParamAuthentication(JWTAuthentication):
    """Accepte le token JWT via le header Authorization OU le query param ?token="""

    def authenticate(self, request):
        token = request.query_params.get('token')
        if token:
            try:
                validated = AccessToken(token)
                user = self.get_user(validated)
                return (user, validated)
            except (InvalidToken, TokenError):
                return None
        return super().authenticate(request)
