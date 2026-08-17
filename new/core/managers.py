from django.contrib.auth.base_user import BaseUserManager


class UserManager(BaseUserManager):
    """
    Users are identified by phone number, not username. Regular signups (via
    SMS) never set a password — `create_user` leaves it unusable in that case.
    Staff accounts get a real one so they can log into /admin.
    """

    def create_user(self, phone_num, password=None, **extra_fields):
        if not phone_num:
            raise ValueError("Users must have a phone number")
        user = self.model(phone_num=phone_num, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, phone_num, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(phone_num, password, **extra_fields)
