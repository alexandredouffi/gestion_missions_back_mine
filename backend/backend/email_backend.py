import ssl
from django.core.mail.backends.smtp import EmailBackend


class BrevoEmailBackend(EmailBackend):
    def open(self):
        if self.connection:
            return False
        connection_params = {
            'host': self.host,
            'port': self.port,
            'local_hostname': None,
        }
        if self.use_ssl:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            connection_params['context'] = ctx
        import smtplib
        self.connection = smtplib.SMTP(**connection_params)
        if self.use_tls:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            self.connection.ehlo()
            self.connection.starttls(context=ctx)
            self.connection.ehlo()
        if self.username and self.password:
            self.connection.login(self.username, self.password)
        return True
