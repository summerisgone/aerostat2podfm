# -*- coding: utf8 -*-
import sys
import os
import re
import requests
import json
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


def strip_inside(text):
    return re.sub('\s+', ' ', text).strip()


def strip_tags(soup):
    return '\n\n'.join([
        strip_inside(p.text) for p in soup
    ])


def merge_files(folder):
    issue = int(re.findall('(\d+)', folder)[0])
    track_filename = 'track_{0}.mp3'.format(issue)
    print '----\nConcatenating files in {0}\n---\n'.format(folder),
    p = Popen('cat "{1}"/*.mp3 > tmp.mp3'.format(issue, folder), shell=True, stdout=PIPE, stderr=PIPE)
    p.wait()
    err = p.stderr.read()
    if err:
        print err
        sys.exit(1)
    print 'fixing bit rate',
    p2 = Popen('vbrfix -ri1 -ri2 -always tmp.mp3 {0}'.format(track_filename), shell=True, stdout=PIPE, stderr=PIPE)
    p2.wait()
    err = p2.stderr.read()
    if err:
        print err
        sys.exit(1)
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
        print 'Error, response code {0}'.format(r.status_code)
        sys.exit(2)

    print r.url
    file_id = re.findall('file_id=(\d+)', r.url)[0]
    print 'OK'
    return file_id


def fetch_description(issue):
    print '{0}. Get description from www.aquarium.ru'.format(issue),
    description_link = 'http://www.aquarium.ru/misc/aerostat/aerostat{0:02d}.html'.format(issue)
    r = requests.get(description_link)
    if not r.status_code == 200:
        print 'Error, response code {0}'.format(r.status_code)
        raise Exception

    soup = BeautifulSoup(r.text)
    body = soup.findAll('table')[0]
    header = body.findAll('p')[0].text
    header = header.replace('\n', ' ').strip()

    issue_text = strip_tags(body.findAll('p')[2:5])
    issue_short = strip_tags(body.findAll('p')[2:3])

    match = re.findall('^(.*)\s+(\d{1,2}\s.*\s\d{4})$', header, re.DOTALL | re.MULTILINE)
    if not match:
        match = re.findall('^(.*),(\d{1,2}\s.*\s\d{4})$', header, re.DOTALL | re.MULTILINE)
    try:
        issue_name, issue_date = match[0]
    except IndexError:
        issue_name, issue_date = [f.text for f in body.findAll('p')[0].findAll('font')]

    issue_date = parse_date(issue_date)
    issue_name = issue_name.strip()

    link = u'\n\n[URL HREF="{0}"]Читать текст[/URL]'.format(description_link)
    track_list = [strip_inside(img.parent.text)for img in body.findAll('img', src="../../kartinki/dot.gif")[1:]]
    issue_text += u'\n\nТреклист:\n'
    issue_text += '\n'.join([track for track in track_list if len(track) < 100])
    issue_text += link
    podcast_data = {
        'day': issue_date.day,
        'month': issue_date.month,
        'year': issue_date.year,
        'number': issue,
        'name': issue_name,
        'short_descr': issue_short.encode('utf8'),
        'body': issue_text.encode('utf8'),
    }
    print 'OK', issue_date
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
        'lent_id': ('%s' % LENT_ID),
        'day': 1,
        'month': 1,
        'year': 2015,
        'number': 999,
        'name': 'undefined',
        'short_descr': 'short',
        'body': 'body',
    }
    data.update(podcast_data)
    r = requests.post('http://aerostatarchive.podfm.ru/actionpodcastadd/',
                      cookies={'PHPSESSID': SESSION_ID},
                      data=data
                      )
    if not r.status_code == 200:
        print 'Error, response code {0}'.format(r.status_code)
        sys.exit(4)
    else:
        print 'OK'


def read_podcast_data(issue):
    with open('{0}.json'.format(issue)) as f:
        return json.loads(f.read())


def upload_podcast(folder):
    # 1. Склеить в файл все треки
    issue, track_filename = merge_files(folder)
    # 2. загрузить файл на /actionuploadpodfile/ через multipart/form-data;
    file_id = upload(track_filename)
    # 3. прочитать описание с сайта аквариума
    podcast_data = read_podcast_data(issue)
    # 4. отправить POST на /actionpodcastadd/
    save_podcast(file_id, podcast_data)


def save_descriptions():
    for num in range(1, 500):
        try:
            data = fetch_description(num)
            with open('{0}.json'.format(num), 'w') as f:
                f.write(json.dumps(data))
        except Exception, e:
            print 'error in ', num, e


def check_json():
    global num, fname, f, data
    for num in range(1, 500):
        fname = '{0}.json'.format(num)
        if os.path.exists(fname):
            with open(fname) as f:
                data = json.loads(f.read())
                # print num, data['year'], data['month'], data['day']
        else:
            print 'Missing ', num


def main(root):
    for folder in sorted(os.listdir(root), key=lambda s:s)[:10]:
        upload_podcast(join(root, folder))


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print 'Usage: python main.py fetch|status|upload [folder]'
        sys.exit(1)

    command = sys.argv[1]
    if command == 'fetch':
        save_descriptions()
    elif command == 'status':
        check_json()
    elif command == 'upload':
        if len(sys.argv) < 2:
            root = join(dirname(__file__), 'music')
        else:
            root = sys.argv[2]
        main(root)
    else:
        print 'Unknown command'
