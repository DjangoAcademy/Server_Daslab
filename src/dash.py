from collections import defaultdict
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import operator
import os
import pickle
import pytz
import simplejson
import subprocess
import time
import traceback

import boto.ec2.cloudwatch
import dropbox
import gviz_api
from github import Github
import requests
from slacker import Slacker

from src.console import *
from src.env import error400, error500
from src.settings import *


def cache_aws(request):
    if request['qs'] == 'init':
        dict_aws = {
            'ec2': [],
            'elb': [],
            'ebs': [],
            'table': [],
        }
        conn = boto.ec2.connect_to_region(
            AWS['REGION'],
            aws_access_key_id=AWS['ACCESS_KEY_ID'], aws_secret_access_key=AWS['SECRET_ACCESS_KEY'], is_secure=True
        )

        resvs = conn.get_only_instances()
        for i, resv in enumerate(resvs):
            sub_conn = boto.ec2.cloudwatch.connect_to_region(
                AWS['REGION'],
                aws_access_key_id=AWS['ACCESS_KEY_ID'], aws_secret_access_key=AWS['SECRET_ACCESS_KEY'], is_secure=True
            )
            data = sub_conn.get_metric_statistics(
                600, datetime.utcnow() - timedelta(hours=2), datetime.utcnow(),
                'CPUCreditBalance', 'AWS/EC2', 'Average', {'InstanceId': resv.id}, 'Count'
            )
            avg = 0
            for d in data:
                avg += d[u'Average']
            if len(data):
                avg = avg / len(data)
            name = resv.tags['Name'] if 'Name' in resv.tags else ''
            dict_aws['ec2'].append({
                'name': name,
                'type': resv.instance_type,
                'dns': resv.dns_name,
                'status': resv.state_code,
                'arch': resv.architecture,
                'region': resv.placement,
                'credit':  '%.1f' % avg,
                'id': resv.id,
            })

        resvs = conn.get_all_volumes()
        for i, resv in enumerate(resvs):
            name = resv.tags['Name'] if 'Name' in resv.tags else ''
            dict_aws['ebs'].append({
                'name': name,
                'size': resv.size,
                'type': resv.type,
                'region': resv.zone,
                'encrypted': resv.encrypted,
                'status': resv.status,
                'id': resv.id,
            })

        conn = boto.ec2.elb.connect_to_region(
            AWS['REGION'],
            aws_access_key_id=AWS['ACCESS_KEY_ID'], aws_secret_access_key=AWS['SECRET_ACCESS_KEY'], is_secure=True
        )
        resvs = conn.get_all_load_balancers()
        for i, resv in enumerate(resvs):
            sub_conn = boto.ec2.cloudwatch.connect_to_region(
                AWS['REGION'],
                aws_access_key_id=AWS['ACCESS_KEY_ID'], aws_secret_access_key=AWS['SECRET_ACCESS_KEY'], is_secure=True
            )
            data = sub_conn.get_metric_statistics(
                300, datetime.utcnow() - timedelta(minutes=30), datetime.utcnow(),
                'HealthyHostCount', 'AWS/ELB', 'Maximum', {'LoadBalancerName': resv.name}, 'Count'
            )
            status = True
            for d in data:
                if d[u'Maximum'] < 1:
                    status = False
                    break
            dict_aws['elb'].append({
                'name': resv.name,
                'dns': resv.dns_name,
                'region': ', '.join(resv.availability_zones),
                'status': status,
            })

            if (not status) and BOT['SLACK']['ADMIN']['MSG_AWS_WARN']:
                last_status = True
                if os.path.exists('%s/cache/aws/init.json' % MEDIA_ROOT):
                    init = simplejson.load(open('%s/cache/aws/init.json' % MEDIA_ROOT, 'r'))
                    for elb in init['elb']:
                        if elb['name'] == resv.name:
                            last_status = elb['status']
                            break

                if last_status:
                    result = dash_duty(0)
                    ppls = result['ppls']
                    (who, _) = find_slack_id(ppls['monthly']['amazon']['main'])
                    send_notify_slack(
                        '@' + who,
                        '',
                        [{
                            'fallback': 'AWS WARNING',
                            'mrkdwn_in': ['text'],
                            'color': PATH.PALETTE['pink'],
                            'text': '*`WARNING`*: AWS ELB Server `%s` has *NO* healthy host! @ _%s_\n' % (resv.name, time.ctime()),
                        }]
                    )


        dict_aws['ec2'] = sorted(dict_aws['ec2'], key=operator.itemgetter(u'name'))
        dict_aws['ebs'] = sorted(dict_aws['ebs'], key=operator.itemgetter(u'name'))
        dict_aws['elb'] = sorted(dict_aws['elb'], key=operator.itemgetter(u'name'))

        for i in xrange(max(len(dict_aws['ec2']), len(dict_aws['elb']), len(dict_aws['ebs']))):
            temp = {}
            if i < len(dict_aws['ec2']):
                temp.update({
                    'ec2': {
                        'name': dict_aws['ec2'][i]['name'],
                        'status': dict_aws['ec2'][i]['status'],
                        'id': dict_aws['ec2'][i]['id'],
                    },
                })
            if i < len(dict_aws['ebs']):
                temp.update({
                    'ebs': {
                        'name': dict_aws['ebs'][i]['name'],
                        'status': dict_aws['ebs'][i]['status'],
                        'id': dict_aws['ebs'][i]['id'],
                    },
                })
            if i < len(dict_aws['elb']):
                temp.update({
                    'elb': {
                        'name': dict_aws['elb'][i]['name'],
                        'status': dict_aws['elb'][i]['status'],
                    },
                })
            dict_aws['table'].append(temp)
        return dict_aws
    else:
        qs = request['qs']
        id = request['id']
        tp = request['tp']

        conn = boto.ec2.cloudwatch.connect_to_region(
            AWS['REGION'],
            aws_access_key_id=AWS['ACCESS_KEY_ID'], aws_secret_access_key=AWS['SECRET_ACCESS_KEY'], is_secure=True
        )
        if tp in ['ec2', 'elb', 'ebs']:
            args = {
                'period': 3600,
                'start_time': datetime.utcnow() - timedelta(days=1),
                'end_time': datetime.utcnow(),
            }
        else:
            return error400(request)

        if qs == 'lat':
            args.update({
                'metric': ['Latency'],
                'namespace': 'AWS/ELB',
                'cols': ['Maximum'],
                'dims': {},
                'unit': 'Seconds',
                'calc_rate': False,
            })
        elif qs == 'req':
            args.update({
                'metric': ['RequestCount'],
                'namespace': 'AWS/ELB',
                'cols': ['Sum'],
                'dims': {},
                'unit': 'Count',
                'calc_rate': False,
            })
        elif qs == 'net':
            args.update({
                'metric': ['NetworkIn', 'NetworkOut'],
                'namespace': 'AWS/EC2',
                'cols': ['Sum'],
                'dims': {},
                'unit': 'Bytes',
                'calc_rate': True,
            })
        elif qs == 'cpu':
            args.update({
                'metric': ['CPUUtilization'],
                'namespace': 'AWS/EC2',
                'cols': ['Average'],
                'dims': {},
                'unit': 'Percent',
                'calc_rate': False,
            })
        elif qs == 'disk':
            args.update({
                'metric': ['VolumeWriteBytes', 'VolumeReadBytes'],
                'namespace': 'AWS/EBS',
                'cols': ['Sum'],
                'dims': {},
                'unit': 'Bytes',
                'calc_rate': True,
            })

    if args['namespace'] == 'AWS/ELB':
        args['dims'] = {'LoadBalancerName': id}
    elif args['namespace'] == 'AWS/EC2':
        args['dims'] = {'InstanceId': id}
    elif args['namespace'] == 'AWS/EBS':
        args['dims'] = {'VolumeId': id}
    return aws_call(conn, args, qs)


def dash_aws(request):
    if 'qs' in request.GET and 'id' in request.GET and 'tp' in request.GET and 'tqx' in request.GET:
        qs = request.GET.get('qs')
        id = request.GET.get('id')
        tp = request.GET.get('tp')
        req_id = request.GET.get('tqx').replace('reqId:', '')

        if qs == 'init':
            return simplejson.dumps(simplejson.load(open('%s/cache/aws/init.json' % MEDIA_ROOT, 'r')))
        elif qs in ['cpu', 'net', 'lat', 'req', 'disk']:
            results = pickle.load(open('%s/cache/aws/%s_%s_%s.pickle' % (MEDIA_ROOT, tp, id, qs), 'rb'))
            return results.replace('__REQ_ID__', req_id)
        else:
            return error400(request)
    else:
        return error400(request)


def cache_ga(request):
    if request['qs'] == 'init':
        access_token = requests.post(
            'https://www.googleapis.com/oauth2/v3/token?refresh_token=%s&client_id=%s&client_secret=%s&grant_type=refresh_token' % (
                GA['REFRESH_TOKEN'], GA['CLIENT_ID'], GA['CLIENT_SECRET'])
        ).json()['access_token']
        list_proj = requests.get(
            'https://www.googleapis.com/analytics/v3/management/accountSummaries?access_token=%s' % access_token
        ).json()['items'][0]['webProperties'][::-1]
        url_colon = urllib.quote(':')
        url_comma = urllib.quote(',')
        dict_ga = {'projs': []}

        for proj in list_proj:
            dict_ga['projs'].append({
                'id': proj['profiles'][0]['id'],
                'track_id': proj['id'],
                'name': proj['name'],
                'url': proj['websiteUrl'],
            })

        for j, proj in enumerate(dict_ga['projs']):
            temp = requests.get(
                'https://www.googleapis.com/analytics/v3/data/ga?ids=ga%s%s&start-date=30daysAgo&end-date=yesterday&metrics=ga%ssessionDuration%sga%sbounceRate%sga%spageviewsPerSession%sga%spageviews%sga%ssessions%sga%susers&access_token=%s' % (
                    url_colon, proj['id'], url_colon, url_comma, url_colon, url_comma, url_colon, url_comma, url_colon, url_comma, url_colon, url_comma, url_colon, access_token)
            ).json()['totalsForAllResults']
            for i, key in enumerate(temp):
                ga_key = key[3:]
                if ga_key in ['bounceRate', 'pageviewsPerSession']:
                    curr = '%.2f' % float(temp[key])
                elif ga_key == 'sessionDuration':
                    curr = str(timedelta(seconds=int(float(temp[key]) / 1000)))
                else:
                    curr = '%d' % int(temp[key])
                dict_ga['projs'][j][ga_key] = curr
        return (dict_ga, access_token)
    else:
        url_colon = urllib.quote(':')
        i = 0
        while True:
            temp = requests.get(
                'https://www.googleapis.com/analytics/v3/data/ga?ids=ga%s%s&start-date=30daysAgo&end-date=yesterday&metrics=ga%s%s&dimensions=ga%sdate&access_token=%s' % (
                    url_colon, request['id'], url_colon, request['qs'], url_colon, request['access_token'])
            ).json()
            if 'rows' in temp:
                temp = temp['rows']
                break
            time.sleep(2)
            i += 1
            if i == 3:
                return error500(request)

        data = []
        stats = ['Timestamp']
        if request['qs'] == 'sessions':
            desp = {
                'Timestamp': ('datetime', 'Timestamp'),
                'Samples': ('number', 'Samples'),
                'Unit': ('string', 'Count'),
            }
            fields = ['Sessions']
        else:
            desp = {
                'Timestamp': ('datetime', 'Timestamp'),
                'Samples': ('number', 'Samples'),
                'Unit': ('string', 'Percent'),
            }
            fields = ['percentNewSessions']

        for row in temp:
            data.append({
                u'Timestamp': datetime.strptime(row[0], '%Y%m%d'),
                fields[0]: float(row[1]),
            })
        for field in fields:
            stats.append(field)
            desp[field] = ('number', field)

        data = sorted(data, key=operator.itemgetter(stats[0]))
        data_table = gviz_api.DataTable(desp)
        data_table.LoadData(data)
        return data_table.ToJSonResponse(columns_order=stats, order_by='Timestamp', req_id='__REQ_ID__')


def dash_ga(request):
    if 'qs' in request.GET and 'id' in request.GET and 'tqx' in request.GET:
        qs = request.GET.get('qs')
        id = request.GET.get('id')
        req_id = request.GET.get('tqx').replace('reqId:', '')

        if qs == 'init':
            return simplejson.dumps(simplejson.load(open('%s/cache/ga/init.json' % MEDIA_ROOT, 'r')))
        elif qs in ['sessions', 'percentNewSessions']:
            results = pickle.load(open('%s/cache/ga/%s_%s.pickle' % (MEDIA_ROOT, id, qs), 'rb'))
            return results.replace('__REQ_ID__', req_id)
        else:
            return error400(request)
    else:
        return error400(request)


def cache_git(request):
    # if request.GET.has_key('qs') and request.GET.has_key('repo') and request.GET.has_key('tqx'):
    gh = Github(login_or_token=GIT['ACCESS_TOKEN'])
    qs = request['qs']

    if qs == 'init':
        repos = []
        orgs = ['DasLab', 'hitrace', 'ribokit']
        for org in orgs:
            for repo in gh.get_organization(org).get_repos():
                i = 0
                contribs = repo.get_stats_contributors()
                while (contribs is None and i <= 5):
                    time.sleep(1)
                    contribs = repo.get_stats_contributors()
                    i += 1
                if contribs is None:
                    print '\033[41mERROR\033[0m: Failed to get Stats Contributors for repository \033[94m%s\033[0m.' % repo.name
                    continue

                data = []
                for contrib in contribs:
                    a, d = (0, 0)
                    for w in contrib.weeks:
                        a += w.a
                        d += w.d
                    au = contrib.author.login if contrib.author else '(None)'
                    data.append({
                        u'Contributors': au,
                        u'Commits': contrib.total,
                        u'Additions': a,
                        u'Deletions': d,
                    })

                data = sorted(data, key=operator.itemgetter(u'Commits'), reverse=True)[0:4]
                repos.append({
                    'url': repo.html_url,
                    'private': repo.private,
                    'data': data,
                    'name': repo.name,
                    'org': org,
                })
        return {'git': repos}
    else:
        if qs == 'num':
            name = request['repo']
            repo = gh.get_repo(name)
            created_at = repo.created_at.replace(tzinfo=pytz.utc).astimezone(pytz.timezone(TIME_ZONE)).strftime('%Y-%m-%d %H:%M:%S')
            pushed_at = repo.pushed_at.replace(tzinfo=pytz.utc).astimezone(pytz.timezone(TIME_ZONE)).strftime('%Y-%m-%d %H:%M:%S')

            num_issues = len(
                requests.get(
                    'https://api.github.com/repos/' + name + '/issues?access_token=%s' % GIT['ACCESS_TOKEN']
                ).json()
            )
            num_pulls = len(
                requests.get(
                    'https://api.github.com/repos/' + name + '/pulls?access_token=%s' % GIT['ACCESS_TOKEN']
                ).json()
            )
            num_watchers = len(
                requests.get(
                    'https://api.github.com/repos/' + name + '/watchers?access_token=%s' % GIT['ACCESS_TOKEN']
                ).json()
            )
            num_branches = len(
                requests.get(
                    'https://api.github.com/repos/' + name + '/branches?access_token=%s' % GIT['ACCESS_TOKEN']
                ).json()
            )
            num_forks = len(
                requests.get(
                    'https://api.github.com/repos/' + name + '/forks?access_token=%s' % GIT['ACCESS_TOKEN']
                ).json()
            )
            num_downloads = len(
                requests.get(
                    'https://api.github.com/repos/' + name + '/downloads?access_token=%s' % GIT['ACCESS_TOKEN']
                ).json()
            )
            json = {
                'name': request['repo'],
                'created_at': created_at,
                'pushed_at': pushed_at,
                'num_watchers': num_watchers,
                'num_pulls': num_pulls,
                'num_issues': num_issues,
                'num_branches': num_branches,
                'num_forks': num_forks,
                'num_downloads': num_downloads,
            }
            return simplejson.dumps(json, sort_keys=True, indent=' ' * 4)

        elif qs in ['c', 'ad']:
            repo = gh.get_repo(request['repo'])
            data = []
            desp = {
                'Timestamp': ('datetime', 'Timestamp'),
                'Samples': ('number', 'Samples'),
                'Unit': ('string', 'Count'),
            }
            stats = ['Timestamp']

            if qs == 'c':
                i = 0
                contribs = repo.get_stats_commit_activity()
                while (contribs is None and i <= 5):
                    time.sleep(1)
                    contribs = repo.get_stats_commit_activity()
                    i += 1
                if contribs is None:
                    print '\033[41mERROR\033[0m: Failed to get Stats Commit Activity for repository \033[94m%s\033[0m.' % repo.name
                    return None
                fields = ['Commits']
                for contrib in contribs:
                    data.append({
                        u'Timestamp': contrib.week,
                        u'Commits': sum(contrib.days),
                    })
            elif qs == 'ad':
                i = 0
                contribs = repo.get_stats_code_frequency()
                while (contribs is None and i <= 5):
                    time.sleep(1)
                    contribs = repo.get_stats_code_frequency()
                    i += 1
                if contribs is None:
                    print '\033[41mERROR\033[0m: Failed to get Stats Code Frequency for repository \033[94m%s\033[0m.' % repo.name
                    return None
                fields = ['Additions', 'Deletions']
                for contrib in contribs:
                    data.append({
                        u'Timestamp': contrib.week,
                        u'Additions': contrib.additions,
                        u'Deletions': contrib.deletions,
                    })

            for field in fields:
                stats.append(field)
                desp[field] = ('number', field)

            data = sorted(data, key=operator.itemgetter(stats[0]))
            data_table = gviz_api.DataTable(desp)
            data_table.LoadData(data)
            return data_table.ToJSonResponse(columns_order=stats, order_by='Timestamp', req_id='__REQ_ID__')


def dash_git(request):
    if 'qs' in request.GET and 'repo' in request.GET and 'org' in request.GET and 'tqx' in request.GET:
        qs = request.GET.get('qs')
        repo = request.GET.get('repo')
        org = request.GET.get('org')
        req_id = request.GET.get('tqx').replace('reqId:', '')

        if qs == 'init':
            return simplejson.dumps(simplejson.load(open('%s/cache/git/init.json' % MEDIA_ROOT, 'r')))
        elif qs in ['c', 'ad', 'num']:
            results = pickle.load(open('%s/cache/git/%s+%s_%s.pickle' % (MEDIA_ROOT, org, repo, qs), 'rb'))
            return results.replace('__REQ_ID__', req_id)
        else:
            return error400(request)
    else:
        return error400(request)


def cache_slack(request):
    qs = request['qs']
    sh = Slacker(SLACK['ACCESS_TOKEN'])

    if qs in ['users', 'home']:
        if qs == 'home':
            home_json = simplejson.load(open('%s/cache/slack/home.json' % MEDIA_ROOT))

        response = sh.users.list().body['members']
        owners, admins, users, gones = [], [], [], []
        for resp in response:
            if 'is_bot' in resp and resp['is_bot']:
                continue
            if resp['name'] in ('slackbot', SLACK['BOT_NAME']):
                continue
            if qs == 'home':
                try:
                    presence = sh.users.get_presence(resp['id']).body['presence']
                except Exception:
                    if os.path.exists('%s/cache/slack/home.json' % MEDIA_ROOT):
                        now = datetime.fromtimestamp(time.time())
                        t_home = datetime.fromtimestamp(os.path.getmtime('%s/cache/slack/home.json' % MEDIA_ROOT))
                        if ((now - t_home).seconds >= 7200):
                            send_notify_slack(
                                SLACK['ADMIN_NAME'],
                                '',
                                [{
                                    'fallback': 'ERROR',
                                    'mrkdwn_in': ['text'],
                                    'color': PATH.PALETTE['pink'],
                                    'text': '*`ERROR`*: *pickle_slack()* Connection/SSL Error @ _%s_\n' % time.ctime(),
                                }]
                            )
                    else:
                        send_error_slack(traceback.format_exc(), 'Cache Dashboard Results', '', 'log_cron_cache.log')
                    return {}
            else:
                presence = sh.users.get_presence(resp['id']).body['presence']

            presence = (presence == 'active')
            temp = {
                'name': resp['profile']['real_name'],
                'id': resp['name'],
                'email': resp['profile']['email'],
                'image': resp['profile']['image_24'],
                'presence': presence,
            }
            if qs == 'home':
                for obj in home_json['users']:
                    if obj['id'] == temp['id']:
                        if presence:
                            temp['last_seen'] = datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')
                        elif 'last_seen' in obj:
                            temp['last_seen'] = obj['last_seen']
                        break
                if not resp['deleted']: users.append(temp)
            else:
                if resp['deleted']:
                    gones.append(temp)
                elif resp['is_owner']:
                    owners.append(temp)
                elif resp['is_admin']:
                    admins.append(temp)
                else:
                    users.append(temp)
        json = {
            'users': users,
            'admins': admins,
            'owners': owners,
            'gones': gones,
        }
    elif qs == 'channels':
        response = sh.channels.list().body['channels']
        channels, archives = [], []
        for resp in response:
            temp = {
                'name': resp['name'],
                'num_members': resp['num_members'],
            }
            history = sh.channels.history(channel=resp['id'], count=1000, inclusive=1).body
            temp.update({
                'num_msgs': len(history['messages']),
                'has_more': history['has_more'],
            })
            num_files = 0
            latest = 0
            for msg in history['messages']:
                if 'file' in msg:
                    num_files += 1
                latest = max(latest, float(msg['ts']))
            latest = datetime.fromtimestamp(latest).strftime('%Y-%m-%d %H:%M:%S')
            temp.update({
                'latest': latest,
                'num_files': num_files,
            })
            if resp['is_archived']:
                archives.append(temp)
            else:
                channels.append(temp)
        json = {
            'channels': channels,
            'archives': archives,
        }
    elif qs == 'files':
        types = ['all', 'pdfs', 'images', 'gdocs', 'zips', 'posts', 'snippets']
        nums, sizes = [], []
        for t in types:
            response = sh.files.list(count=100, types=t).body
            size = 0
            for i in xrange(response['paging']['pages']):
                page = sh.files.list(count=100, types=t, page=i).body['files']
                for p in page:
                    size += p['size']
            nums.append(response['paging']['total'])
            sizes.append(size)
        json = {
            'files': {
                'types': types,
                'nums': nums,
                'sizes': sizes,
            },
        }

    elif qs in ['plot_files', 'plot_msgs']:
        desp = {
            'Timestamp': ('datetime', 'Timestamp'),
            'Samples': ('number', 'Samples'),
            'Unit': ('string', 'Count'),
        }
        stats = ['Timestamp']
        data = []

        if qs == 'plot_files':
            fields = ['Files']
            for i in xrange(7):
                start_time = datetime.today() - timedelta(days=i + 1)
                end_time = start_time + timedelta(days=1)
                num = sh.files.list(
                    types='all',
                    ts_from=time.mktime(start_time.timetuple()), ts_to=time.mktime(end_time.timetuple())
                ).body['paging']['total']
                data.append({
                    u'Timestamp': end_time.replace(hour=0, minute=0, second=0, microsecond=0),
                    u'Files': num,
                })
        elif qs == 'plot_msgs':
            fields = ['Messages']
            response = sh.channels.list().body['channels']
            for resp in response:
                if resp['is_archived']:
                    continue
                for i in xrange(7):
                    start_time = datetime.today() - timedelta(days=i + 1)
                    end_time = start_time + timedelta(days=1)
                    num = len(
                        sh.channels.history(
                            channel=resp['id'],
                            latest=time.mktime(end_time.timetuple()), oldest=time.mktime(start_time.timetuple()),
                            count=1000
                        ).body['messages']
                    )
                    if len(data) > i:
                        data[i]['Messages'] += num
                    else:
                        data.append({
                            u'Timestamp': end_time.replace(hour=0, minute=0, second=0, microsecond=0),
                            u'Messages': num,
                        })
                    time.sleep(2)

        for field in fields:
            stats.append(field)
            desp[field] = ('number', field)

        data = sorted(data, key=operator.itemgetter(stats[0]))
        data_table = gviz_api.DataTable(desp)
        data_table.LoadData(data)
        return data_table.ToJSonResponse(columns_order=stats, order_by='Timestamp', req_id='__REQ_ID__')

    return json


def dash_slack(request):
    if 'qs' in request.GET and 'tqx' in request.GET:
        qs = request.GET.get('qs')
        req_id = request.GET.get('tqx').replace('reqId:', '')

        if qs in ['users', 'home', 'channels', 'files']:
            return simplejson.dumps(simplejson.load(open('%s/cache/slack/%s.json' % (MEDIA_ROOT, qs), 'r')))
        elif qs in ['plot_files', 'plot_msgs']:
            results = pickle.load(open('%s/cache/slack/%s.pickle' % (MEDIA_ROOT, qs), 'rb'))
            return results.replace('__REQ_ID__', req_id)
        else:
            return error400(request)
    else:
        return error400(request)


def cache_dropbox(request):
    qs = request['qs']
    dh = dropbox.Dropbox(DROPBOX['ACCESS_TOKEN'])

    if qs == 'sizes':
        usage = dh.users_get_space_usage()
        json = {
            'quota_used': usage.used,
            'quota_all': usage.allocation.get_individual().allocated,
        }
        json.update({
            'quota_avail': (json['quota_all'] - json['quota_used']),
        })
        return json

    elif qs == 'folders':
        json = []
        sizes = {}
        cursor = None
        result = dh.files_list_folder('', recursive=True, include_media_info=True)
        while result.has_more:
            for metadata in result.entries:
                if isinstance(metadata, dropbox.files.FileMetadata):
                    sizes[metadata.path_display] = metadata.size
            result = dh.files_list_folder_continue(result.cursor)

        folder_sizes = defaultdict(lambda: 0)
        folder_nums = defaultdict(lambda: 0)
        for path, size in sizes.items():
            segments = path.split('/')
            for i in xrange(1, len(segments)):
                folder = '/'.join(segments[:i])
                if folder == '':
                    folder = '/'
                folder_sizes[folder] += size
                folder_nums[folder] += 1

        # shares = requests.get('https://api.dropboxapi.com/1/shared_folders/?include_membership=True&access_token=%s' % DROPBOX['ACCESS_TOKEN']).json()

        folder_shares = defaultdict(lambda: 0)
        result = dh.sharing_list_folders()
        for metadata in result.entries:
            folder_shares[metadata.name] = len(f['membership'])
        while result.cursor:
            for metadata in result.entries:
                print metadata
            result = dh.sharing_list_folders_continue(result.cursor)


        for folder in sorted(folder_sizes.keys()):
            if folder == '/' or '/' in folder[1:]:
                continue
            result = dh.metadata(folder, list=False)
            latest = datetime.strptime(result['modified'][:-6], '%a, %d %b %Y %H:%M:%S').replace(tzinfo=pytz.utc).astimezone(pytz.timezone(TIME_ZONE)).strftime('%Y-%m-%d %H:%M:%S')
            json.append({
                'name': result['path'][1:],
                'nums': folder_nums[folder],
                'sizes': folder_sizes[folder],
                'shares': folder_shares[folder[1:]],
                'latest': latest,
            })
        return {'folders': json}

    elif qs == 'history':
        desp = {
            'Timestamp': ('datetime', 'Timestamp'),
            'Samples': ('number', 'Samples'),
            'Unit': ('string', 'Count'),
        }
        stats = ['Timestamp']
        data = []
        fields = ['Files']

        sizes = {}
        cursor = None
        while cursor is None or result['has_more']:
            result = dh.delta(cursor)
            for path, metadata in result['entries']:
                sizes[path] = metadata['modified'] if metadata else 0
            cursor = result['cursor']

        temp = {}
        for i in xrange(8):
            ts = (datetime.utcnow() - timedelta(days=i)).replace(tzinfo=pytz.utc).astimezone(pytz.timezone(TIME_ZONE)).replace(hour=0, minute=0, second=0, microsecond=0)
            temp.update({ts: 0})
        for path, ts in sizes.items():
            ts = datetime.strptime(ts[:-6], '%a, %d %b %Y %H:%M:%S').replace(tzinfo=pytz.utc).astimezone(pytz.timezone(TIME_ZONE))
            for i in xrange(7):
                ts_u = (datetime.utcnow() - timedelta(days=i)).replace(tzinfo=pytz.utc).astimezone(pytz.timezone(TIME_ZONE)).replace(hour=0, minute=0, second=0, microsecond=0)
                ts_l = (datetime.utcnow() - timedelta(days=i+1)).replace(tzinfo=pytz.utc).astimezone(pytz.timezone(TIME_ZONE)).replace(hour=0, minute=0, second=0, microsecond=0)
                if ts_l < ts <= ts_u:
                    temp[ts_u] += 1
                    break
        data = []
        for ts in temp.keys():
            data.append({
                u'Timestamp': ts,
                u'Files': temp[ts],
            })

        for field in fields:
            stats.append(field)
            desp[field] = ('number', field)

        data = sorted(data, key=operator.itemgetter(stats[0]))
        data_table = gviz_api.DataTable(desp)
        data_table.LoadData(data)
        return data_table.ToJSonResponse(columns_order=stats, order_by='Timestamp', req_id='__REQ_ID__')


def dash_dropbox(request):
    if 'qs' in request.GET and 'tqx' in request.GET:
        qs = request.GET.get('qs')
        req_id = request.GET.get('tqx').replace('reqId:', '')

        if qs in ['sizes', 'folders']:
            return simplejson.dumps(simplejson.load(open('%s/cache/dropbox/%s.json' % (MEDIA_ROOT, qs), 'r')))
        elif qs == 'history':
            results = pickle.load(open('%s/cache/dropbox/history.pickle' % MEDIA_ROOT, 'rb'))
            return results.replace('__REQ_ID__', req_id)
        else:
            return error400(request)
    else:
        return error400(request)


def dash_ssl():
    try:
        subprocess.check_call(
            'echo | openssl s_client -connect %s:443 | openssl x509 -noout -enddate > %s' % (env('SSL_HOST'), os.path.join(MEDIA_ROOT, 'data/temp.txt')),
            shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        exp_date = subprocess.Popen(
            'sed \'s/^notAfter\=//g\' %s' % os.path.join(MEDIA_ROOT, 'data/temp.txt'),
            shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        ).communicate()[0].strip()
        subprocess.check_call('rm %s' % os.path.join(MEDIA_ROOT, 'data/temp.txt'), shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError:
        send_error_slack(traceback.format_exc(), 'Check SSL Certificate', 'dash_ssl', 'log_cron.log')

    exp_date = datetime.strptime(exp_date.replace('notAfter=', ''), '%b %d %H:%M:%S %Y %Z').strftime('%Y-%m-%d %H:%M:%S')
    return exp_date


def get_spreadsheet(prefix, id, suffix):
    try:
        subprocess.check_call(
            '%s && drive download --format csv --force -i %s && %s' % (prefix, id, suffix),
            shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        return True
    except subprocess.CalledProcessError:
        return False


def cache_schedule():
    gdrive_dir = 'cd %s/cache' % MEDIA_ROOT
    gdrive_mv = 'mv Das\ Group\ Meeting\ Schedule.csv schedule.csv'

    flag = get_spreadsheet(gdrive_dir, DRIVE['SCHEDULE_SPREADSHEET_ID'], gdrive_mv)
    i = 0
    while (not flag and i <= 3):
        time.sleep(5)
        flag = get_spreadsheet(gdrive_dir, DRIVE['SCHEDULE_SPREADSHEET_ID'], gdrive_mv)
        i += 1

    if not flag:
        send_notify_slack(
            SLACK['ADMIN_NAME'],
            '',
            [{
                'fallback': 'ERROR',
                'mrkdwn_in': ['text'],
                'color': PATH.PALETTE['pink'],
                'text': '*`ERROR`*: *cache_schedule()* Download Failure @ _%s_\n' % time.ctime(),
            }]
        )
        # send_error_slack(traceback.format_exc(), 'Download Schedule Spreadsheet', 'cache_schedule', 'log_cron_cache.log')
        if os.path.exists('%s/cache/schedule.json' % MEDIA_ROOT):
            now = datetime.fromtimestamp(time.time())
            t_sch = datetime.fromtimestamp(os.path.getmtime('%s/cache/schedule.json' % MEDIA_ROOT))
            if (now - t_sch).seconds >= 7200:
                raise Exception('Error with downloading schedule spreadsheet.')
            else:
                return

    try:
        lines = open('%s/cache/schedule.csv' % MEDIA_ROOT, 'r').readlines()
        this = ''
        tp = lines[0].split(',')[5]
        place = tp[tp.rfind('@')+1:].strip()[:-1]
        week_day = tp[1:tp.find('@')].strip().lower()
        week_day = ['sunday', 'monday', 'tueday', 'wednesday', 'thursday', 'friday', 'saturday'].index(week_day)

        tp = tp[tp.find('@')+1:tp.rfind('@')].strip()
        t_start = tp[:tp.find('-')].strip()
        t_end = tp[tp.find('-')+1:].strip()

        for row in lines:
            row = row.split(',')
            if this:
                next = {
                    'date': datetime.strptime(row[1], '%m/%d/%Y').strftime('%b %d'),
                    'type': row[2],
                    'who': row[3],
                    'note': row[5],
                }
                break
            if len(row) >= 7 and '[THIS WEEK]' in row[6]:
                this = {
                    'date': datetime.strptime(row[1], '%m/%d/%Y').strftime('%b %d'),
                    'type': row[2],
                    'who': row[3],
                    'note': row[5],
                }

        if not this:
            raise Exception('Error with parsing spreadsheet csv: no [THIS WEEK] found.')
        for row in reversed(lines):
            row = row.split(',')
            if len(row) == 10 and any(row):
                last = {
                    'date': datetime.strptime(row[1], '%m/%d/%Y').strftime('%b %d'),
                    'type': row[2],
                    'who': row[3],
                    'note': row[5],
                }
                break

        subprocess.check_call(
            'rm %s/cache/schedule.csv' % MEDIA_ROOT,
            shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        return {
            'last': last,
            'this': this,
            'next': next,
            'place': place,
            'time': {
                'start': t_start,
                'end': t_end,
            },
            'weekday': week_day,
        }
    except Exception:
        send_error_slack(traceback.format_exc(), 'Parse Schedule Spreadsheet', 'cache_schedule', 'log_cron_cache.log')

def dash_schedule(request):
    return simplejson.load(open('%s/cache/schedule.json' % MEDIA_ROOT, 'r'))


def cache_duty():
    gdrive_dir = 'cd %s/cache' % MEDIA_ROOT
    gdrive_mv = 'mv Das\ Lab\ Responsibilities.csv duty.csv'

    flag = get_spreadsheet(gdrive_dir, DRIVE['DUTY_SPREADSHEET_ID'], gdrive_mv)
    i = 0
    while (not flag and i <= 3):
        time.sleep(5)
        flag = get_spreadsheet(gdrive_dir, DRIVE['DUTY_SPREADSHEET_ID'], gdrive_mv)
        i += 1

    if not flag:
        send_notify_slack(
            SLACK['ADMIN_NAME'],
            '',
            [{
                'fallback': 'ERROR',
                'mrkdwn_in': ['text'],
                'color': PATH.PALETTE['pink'],
                'text': '*`ERROR`*: *cache_duty()* Download Failure @ _%s_\n' % time.ctime(),
            }]
        )
        # send_error_slack(traceback.format_exc(), 'Download Duty Spreadsheet', 'cache_duty', 'log_cron_cache.log')
        if os.path.exists('%s/cache/duty.json' % MEDIA_ROOT):
            now = datetime.fromtimestamp(time.time())
            t_sch = datetime.fromtimestamp(os.path.getmtime('%s/cache/duty.json' % MEDIA_ROOT))
            if (now - t_sch).seconds >= 7200:
                raise Exception('Error with downloading duty spreadsheet.')
            else:
                return

    try:
        lines = open('%s/cache/duty.csv' % MEDIA_ROOT, 'r').readlines()
        ppls = {
            'weekly': {},
            'monthly': {},
            'quarterly': {},
        }
        jobs = ['birthday', 'breakfast', 'eterna', 'group meeting', 'flash slide', 'lab trips', 'amazon', 'website', 'github']
        n_jobs = next(i for (i, x) in enumerate(lines) if not x.strip().replace(',', ''))
        for row in lines[1:n_jobs]:
            row = row.split(',')
            for job in jobs:
                if job in row[0].lower():
                    ppls[row[1].lower()][job] = {
                        'main': row[2],
                        'backup': row[3],
                    }
                    break
        subprocess.check_call('rm %s/cache/duty.csv' % MEDIA_ROOT, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        return {
            'jobs': jobs,
            'ppls': ppls,
        }
    except Exception:
        send_error_slack(traceback.format_exc(), 'Parse Duty Spreadsheet', 'cache_duty', 'log_cron_cache.log')

def dash_duty(request):
    return simplejson.load(open('%s/cache/duty.json' % MEDIA_ROOT, 'r'))


def get_calendar():
    try:
        subprocess.check_call(
            'curl --silent --request GET \'%s\' -o %s/cache/calendar.ics' % (GCAL['ICS'], MEDIA_ROOT),
            shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        return True
    except subprocess.CalledProcessError:
        return False

def cache_cal():
    flag = get_calendar()
    i = 0
    while (not flag and i <= 3):
        time.sleep(5)
        flag = get_calendar()
        i += 1

    if not flag:
        send_error_slack(traceback.format_exc(), 'Download Calendar ICS', 'cache_cal', 'log_cron_cache.log')
        if os.path.exists('%s/cache/calendar.json' % MEDIA_ROOT):
            now = datetime.fromtimestamp(time.time())
            t_cal = datetime.fromtimestamp(os.path.getmtime('%s/cache/calendar.json' % MEDIA_ROOT))
            if (now - t_cal).seconds >= 7200:
                raise Exception('Error with downloading calendar ICS file.')
            else:
                return

    try:
        ics = open('%s/cache/calendar.ics' % MEDIA_ROOT, 'r').readlines()
        cal = Calendar.from_ical(''.join(ics))
        data = []
        format_UTC = '%Y-%m-%d %H:%M:%S'
        for event in cal.walk('vevent'):
            title = event.get('SUMMARY')
            start = event.get('DTSTART').dt
            if isinstance(start, datetime):
                if 'TZID' in event.get('DTSTART').params:
                    start = start.replace(tzinfo=pytz.timezone(event.get('DTSTART').params['TZID'])).astimezone(pytz.timezone(TIME_ZONE))
                else:
                    start = start.replace(tzinfo=pytz.utc).astimezone(pytz.timezone(TIME_ZONE))
            if 'DTEND' in event:
                end = event.get('DTEND').dt
                if isinstance(end, datetime):
                    if 'TZID' in event.get('DTEND').params:
                        end = end.replace(tzinfo=pytz.timezone(event.get('DTSTART').params['TZID'])).astimezone(pytz.timezone(TIME_ZONE))
                    else:
                        end = end.replace(tzinfo=pytz.utc).astimezone(pytz.timezone(TIME_ZONE))
            else:
                end = start + relativedelta(hours=1)

            all_day = (not isinstance(start, datetime))
            color = '#' + PATH.PALETTE['green'] if all_day else '#' + PATH.PALETTE['blue']
            if ('group meeting' in title.lower() or
                'das lab group' in title.lower() or
                'eterna dev meeting' in title.lower()):
                color = '#' + PATH.PALETTE['red']
            if ('BD' in title or
                'b-day' in title or
                'birthday' in title.lower()):
                color = '#' + PATH.PALETTE['violet']
            data.append({
                'title': title,
                'start': datetime.strftime(start, format_UTC),
                'end': datetime.strftime(end, format_UTC),
                'allDay': all_day,
                'color': color,
            })

            if ('RRULE' in event and
                'FREQ' in event.get('RRULE')):
                rrule = event.get('RRULE')
                while True:
                    if 'YEARLY' in rrule['FREQ']:
                        if 'INTERVAL' in rrule:
                            interval = rrule['INTERVAL'][0]
                        else:
                            interval = 1
                        start += relativedelta(years=interval)
                        end += relativedelta(years=interval)
                    elif 'MONTHLY' in rrule['FREQ']:
                        if 'INTERVAL' in rrule:
                            interval = rrule['INTERVAL'][0]
                        else:
                            interval = 1
                        start += relativedelta(months=interval)
                        end += relativedelta(months=interval)
                    elif 'WEEKLY' in rrule['FREQ']:
                        if 'INTERVAL' in rrule:
                            interval = rrule['INTERVAL'][0]
                        else:
                            interval = 1
                        start += timedelta(days=7*interval)
                        end += timedelta(days=7*interval)
                    elif 'DAILY' in rrule['FREQ']:
                        if 'INTERVAL' in rrule:
                            interval = rrule['INTERVAL'][0]
                        else:
                            interval = 1
                        start += timedelta(days=interval)
                        end += timedelta(days=interval)
                    else:
                        break

                    until = (datetime.today() + relativedelta(years=2)).date()
                    if 'UNTIL' in rrule:
                        until = rrule['UNTIL'][0]
                        if isinstance(until, datetime):
                            until = until.date()

                    if all_day:
                        if start > until:
                            break
                    else:
                        if start.date() > until:
                            break

                    data.append({
                        'title': title,
                        'start': datetime.strftime(start, format_UTC),
                        'end': datetime.strftime(end, format_UTC),
                        'allDay': all_day,
                        'color': color,
                    })

        subprocess.check_call(
            'rm %s/cache/calendar.ics' % MEDIA_ROOT,
            shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        return data
    except Exception:
        send_error_slack(traceback.format_exc(), 'Parse Calendar ICS', 'cache_cal', 'log_cron_cache.log')

        if os.path.exists('%s/cache/calendar.pickle' % MEDIA_ROOT):
            now = datetime.fromtimestamp(time.time())
            t_cal = datetime.fromtimestamp(os.path.getmtime('%s/cache/calendar.pickle' % MEDIA_ROOT))
            if (now - t_cal).seconds >= 7200:
                if IS_SLACK:
                    send_notify_slack(
                        SLACK['ADMIN_NAME'],
                        '',
                        [{
                            'fallback': 'ERROR',
                            'mrkdwn_in': ['text'],
                            'color': PATH.PALETTE['red'],
                            'text': '*`ERROR`*: *cache_cal()* @ _%s_\n>```%s```\n' % (time.ctime(), err),
                        }]
                    )
        subprocess.check_call(
            'cp %s/cache/calendar.ics %s/cache/calendar_%s.ics' % (MEDIA_ROOT, MEDIA_ROOT, int(time.time())),
            shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        subprocess.check_call(
            'rm %s/cache/calendar.ics' % MEDIA_ROOT,
            shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        raise Exception('Error with parsing calendar ICS.')


def dash_cal():
    return simplejson.dumps(simplejson.load(open('%s/cache/calendar.json' % MEDIA_ROOT, 'r')))


def format_dash_ts(rel_path, interval):
    now = datetime.fromtimestamp(time.time())
    if os.path.exists('%s/cache/%s' % (MEDIA_ROOT, rel_path)):
        t = datetime.fromtimestamp(os.path.getmtime('%s/cache/%s' % (MEDIA_ROOT, rel_path)))
        if (now - t).seconds >= int(interval) * 2.5 * 60:
            t = '<span class="label label-danger">' + t.strftime('%Y-%m-%d %H:%M:%S') + '</span>'
        else:
            t = '<span class="label label-primary">' + t.strftime('%Y-%m-%d %H:%M:%S') + '</span>'
    else:
        t = '<span class="label label-default">N/A</span>'
    return t
