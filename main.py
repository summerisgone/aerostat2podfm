# -*- coding: utf8 -*-
import sys
import os
import re
import requests
from os.path import join, dirname
from bs4 import BeautifulSoup
from dateutil.parser import parse
from subprocess import Popen, PIPE


LENT_ID = '57430'
SESSION_ID = os.environ['SESSION_ID']


def parse_date(source):
    source = source.replace(u'января', u'Jan')
    source = source.replace(u'февраля', u'Feb')
    source = source.replace(u'марта', u'Mar')
    source = source.replace(u'апреля', u'Apr')
    source = source.replace(u'мая', u'May')
    source = source.replace(u'июня', u'Jun')
    source = source.replace(u'июля', u'Jul')
    source = source.replace(u'августа', u'Aug')
    source = source.replace(u'сентября', u'Sep')
    source = source.replace(u'октября', u'Oct')
    source = source.replace(u'ноября', u'Nov')
    source = source.replace(u'декабря', u'Dec')
    source = source.strip()
    return parse(source)


def trim_inside(soup):
    return '\n\n'.join([
        re.sub('\s+', ' ', p.text) for p in soup
    ])


def merge_files(folder):
    issue = int(re.findall('(\d+)', folder)[0])
    track_filename = 'track_{0}.mp3'.format(issue)
    print '----\nConcatenating files in {0}\n---\n'.format(folder),
    p = Popen('cat "{1}"/*.mp3 > tmp.mp3'.format(issue, folder), shell=True, stdout=PIPE, stderr=PIPE)
    p.wait()
    print 'fixing bit rate',
    p2 = Popen('vbrfix -ri1 -ri2 -always tmp.mp3 {0}'.format(track_filename), shell=True, stdout=PIPE, stderr=PIPE)
    p2.wait()
    print 'OK'
    return issue, track_filename

def upload(track_filename):
    print '2. upload file to podfm',
    files = {'file': (track_filename, open(track_filename, 'rb'), 'audio/mpeg')}
    r = requests.post('http://aerostatarchive.podfm.ru/actionuploadpodfile/',
                      params={'todo': 'step1_upload'},
                      files=files,
                      cookies=dict(PHPSESSID=('%s' % SESSION_ID)))
    # r.url = u'http://aerostatarchive.podfm.ru/podcastedit/?file_id=390711'
    if not r.status_code == 200:
        print 'Error, response code != 200'
        sys.exit(2)
    else:
        print 'OK'
    file_id = re.findall('file_id=(\d+)', r.url)[0]
    return file_id


def fetch_description(issue):
    print '3. Get description from www.aquarium.ru',
    r = requests.get('http://www.aquarium.ru/misc/aerostat/aerostat{0:02d}.html'.format(issue))
    if not r.status_code == 200:
        print 'Error, reponse code != 200'
        sys.exit(3)
    else:
        print 'OK'
    soup = BeautifulSoup(r.text)
    body = soup.findAll('table')[0].tr.td
    header = body.findAll('p')[0].text
    issue_text = trim_inside(body.findAll('p')[2:])
    issue_short = trim_inside(body.findAll('p')[2:3])
    issue_name, issue_date = header.rsplit(',', 1)
    issue_date = parse_date(issue_date)
    podcast_data = {
        'day': issue_date.day,
        'month': issue_date.month,
        'year': issue_date.year,
        'number': issue,
        'name': issue_name,
        'short_descr': issue_short.encode('utf8'),
        'body': issue_text.encode('utf8'),
        'lent_id': ('%s' % LENT_ID),

    }
    return podcast_data


def save_podcast(file_id, podcast_data):
    print '4. create podcast on podfm.ru',
    data = {
        'todo': 'save',
        'make_slide': 'off',
        'hour': '0',
        'min': '0',
        'format': '1',
        'cat_id': '27',
        'file_id': file_id,
    }
    data.update(podcast_data)
    r = requests.post('http://aerostatarchive.podfm.ru/actionpodcastadd/',
                      cookies={'PHPSESSID': SESSION_ID},
                      data=data
                      )
    if not r.status_code == 200:
        print 'Error, response code != 200'
        sys.exit(4)
    else:
        print 'OK'


def main(folder):
    # 1. Склеить в файл все треки
    issue, track_filename = merge_files(folder)
    # 2. загрузить файл на /actionuploadpodfile/ через multipart/form-data;
    file_id = upload(track_filename)
    # 3. Загрузить описание с сайта аквариума
    podcast_data = fetch_description(issue)
    # 4. отправить POST на /actionpodcastadd/
    save_podcast(file_id, podcast_data)


if __name__ == '__main__':
    for folder in sorted(os.listdir('music'), key=lambda x: x):
        main(join(dirname(__file__), 'music', folder))
