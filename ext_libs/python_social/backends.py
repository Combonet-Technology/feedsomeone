from social_core.backends.linkedin import LinkedinOAuth2 as BaseLinkedinOAuth2


class LinkedinOAuth2(BaseLinkedinOAuth2):
    """Allow LinkedIn's exact callback URI to differ from the request host."""

    def get_redirect_uri(self, state=None):
        redirect_uri = self.setting('REDIRECT_URI')
        if redirect_uri:
            return redirect_uri
        return super().get_redirect_uri(state)
