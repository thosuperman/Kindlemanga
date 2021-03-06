from __future__ import absolute_import, unicode_literals
import os
import logging
import shlex
import shutil
import subprocess
import time

from django.conf import settings
from celery import group, chord, chain
from celery.decorators import task
from PIL import Image
import requests
from mediafire.client import MediaFireClient, File, Folder

from .utils import url2filename, extract_images_url
from .models import Manga, Volume, Chapter

client = MediaFireClient()
client.login(email=settings.MEDIAFIRE_EMAIL, password=settings.MEDIAFIRE_PASSWORD, app_id='42511')
UPLOAD_FOLDER = settings.MEDIAFIRE_FOLDER

# https://stackoverflow.com/questions/31784484/how-to-parallelized-file-downloads
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')


def download(chapter_id, index, path, url):
    filename = url2filename(url, chapter_id, index)
    logging.debug('downloading %s', filename)
    r = requests.get(url, stream=True)
    if r.status_code == 200:
        with open(os.path.join(path, filename), 'wb') as f:
            for chunk in r:
                f.write(chunk)


@task(name="download_chapter")
def download_chapter(path, chapter_id):
    c = Chapter.objects.get(id=chapter_id)
    urls = extract_images_url(c.source)
    for index, url in enumerate(urls):
        download(chapter_id, index, path, url)


def make_volume_dir(volume_id):
    v = Volume.objects.get(id=volume_id)
    path = os.path.join('/tmp/Manga', v.__str__())
    os.makedirs(path, exist_ok=True)
    return path


def extract_chapters(volume_id):
    v = Volume.objects.get(id=volume_id)
    chapters = v.chapter_set.all()
    return chapters


@task(name="download_volume")
def download_volume(volume_id):
    path = make_volume_dir(volume_id)
    chapters = extract_chapters(volume_id)
    g = group(download_chapter.si(path, chap.id) for chap in chapters)()
    return path


@task(name="generate_manga")
def generate_manga(path, profile='KV'):
    time.sleep(45)
    args = shlex.split('kcc-c2e -m -q -p {0} -f MOBI {1}'.format(profile, shlex.quote(path)))
    p = subprocess.Popen(args, stdout=subprocess.PIPE)
    p.communicate()
    return "{}.mobi".format(path)


@task(name="delete_corrupt_file")
def delete_corrupt_file(path):
    for filename in os.listdir(path):
        try:
            img = Image.open(os.path.join(path, filename))
            img.verify()
        except (IOError, SyntaxError) as e:
            os.remove(os.path.join(path, filename))

    return path


@task(name="upload_and_save")
def upload_and_save(path, volume_id):
    v = Volume.objects.get(id=volume_id)
    r = client.upload_file(path, UPLOAD_FOLDER)
    link = "http://www.mediafire.com/file/{}".format(r.quickkey)
    v.download_link = link
    v.save()
    shutil.rmtree(path.split('.mobi')[0])
    os.remove(path)


def make_volume(volume_id):
    res = chain(
        download_volume.s(volume_id),
        delete_corrupt_file.s(),
        generate_manga.s(),
        upload_and_save.s(volume_id)
    )()
    return res
