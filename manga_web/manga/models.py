from django.db import models
from django.template.defaultfilters import slugify


class Manga(models.Model):
    name = models.CharField(max_length=255, null=False)
    source = models.URLField(max_length=500, null=False)
    total_chap = models.IntegerField(null=True)
    image_src = models.URLField(max_length=500, null=True)
    slug = models.SlugField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.name)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super(Manga, self).save(*args, **kwargs)


class Volume(models.Model):
    manga = models.ForeignKey(Manga, on_delete=models.CASCADE)
    number = models.IntegerField(null=True)
    download_link = models.URLField(max_length=500, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "{} - Volume {}".format(self.manga.name, self.number)


class Chapter(models.Model):
    volume = models.ForeignKey(Volume, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    source = models.URLField(max_length=500)

    def __str__(self):
        return "{} - Volume {} - {}".format(
            self.volume.manga.name,
            self.volume.number,
            self.name
        )
