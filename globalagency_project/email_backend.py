import smtplib

from django.conf import settings
from django.core.mail.backends.smtp import EmailBackend as DjangoSMTPEmailBackend
from django.core.mail.message import sanitize_address
from email.utils import parseaddr


class EmailBackend(DjangoSMTPEmailBackend):
    """SMTP backend with a stable HELO name and a clean envelope sender."""

    def open(self):
        if self.connection:
            return False

        local_hostname = getattr(
            settings,
            'EMAIL_LOCAL_HOSTNAME',
            None,
        ) or 'africawesterneducation.com'

        connection_params = {"local_hostname": local_hostname}
        if self.timeout is not None:
            connection_params["timeout"] = self.timeout
        if self.use_ssl:
            connection_params["context"] = self.ssl_context

        try:
            self.connection = self.connection_class(
                self.host, self.port, **connection_params
            )

            if not self.use_ssl and self.use_tls:
                self.connection.starttls(context=self.ssl_context)
            if self.username and self.password:
                self.connection.login(self.username, self.password)
            return True
        except OSError:
            if not self.fail_silently:
                raise

    def _send(self, email_message):
        if not email_message.recipients():
            return False

        encoding = email_message.encoding or settings.DEFAULT_CHARSET
        envelope_from = parseaddr(email_message.from_email or '')[1] or email_message.from_email
        envelope_to = [
            parseaddr(addr)[1] or sanitize_address(addr, encoding)
            for addr in email_message.recipients()
        ]
        message = email_message.message()

        try:
            self.connection.sendmail(
                envelope_from,
                envelope_to,
                message.as_bytes(linesep="\r\n"),
            )
        except smtplib.SMTPException:
            if not self.fail_silently:
                raise
            return False
        return True
