from django.db import models


class Restaurant(models.Model):
    name = models.CharField(max_length=200, unique=True)
    image = models.ImageField(
        upload_to="restaurants/",
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.name
