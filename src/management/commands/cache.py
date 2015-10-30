import pickle
import simplejson
import subprocess
import sys
import time
import traceback

from django.core.management.base import BaseCommand

from src.settings import *
from src.console import *
from src.dash import *


class Command(BaseCommand):
    help = 'Caches Dashboard information on an 3/15/30 minutes interval. Cache files are saved to cache/. Existing files will be overwritten.'

    def pickle_aws(self, request, name):
        f_name = '%s/cache/aws/%s_%s_%s.pickle' % (MEDIA_ROOT, request['tp'], name, request['qs'])
        pickle.dump(cache_aws(request), open(f_name + '_tmp', 'wb'))
        subprocess.check_call("mv %s_tmp %s" % (f_name, f_name), shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    def pickle_ga(self, request):
        f_name = '%s/cache/ga/%s_%s.pickle' % (MEDIA_ROOT, request['id'], request['qs'])
        pickle.dump(cache_ga(request), open(f_name + '_tmp', 'wb'))
        subprocess.check_call("mv %s_tmp %s" % (f_name, f_name), shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    def pickle_git(self, request):
        f_name = '%s/cache/git/%s_%s.pickle' % (MEDIA_ROOT, request['repo'], request['qs'])
        pickle.dump(cache_git(request), open(f_name + '_tmp', 'wb'))
        subprocess.check_call("mv %s_tmp %s" % (f_name, f_name), shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    def pickle_slack(self, request):
        f_name = '%s/cache/slack/%s.pickle' % (MEDIA_ROOT, request['qs'])
        pickle.dump(cache_slack(request), open(f_name + '_tmp', 'wb'))
        subprocess.check_call("mv %s_tmp %s" % (f_name, f_name), shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    def pickle_dropbox(self, request):
        f_name = '%s/cache/dropbox/%s.pickle' % (MEDIA_ROOT, request['qs'])
        pickle.dump(cache_dropbox(request), open(f_name + '_tmp', 'wb'))
        subprocess.check_call("mv %s_tmp %s" % (f_name, f_name), shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


    def add_arguments(self, parser):
        # Positional arguments
        parser.add_argument('int', nargs='+', type=int, help='Interval, choose from (3, 15, 30).')

    def handle(self, *args, **options):
        t0 = time.time()
        self.stdout.write(time.ctime())

        if options['int']:
            is_3, is_15, is_30 = False, False, False
            is_3 = (options['int'][0] == 3)
            is_15 = (options['int'][0] == 15)
            is_30 = (options['int'][0] == 30)
        else:
            is_3, is_15, is_30 = True, True, True

        try:
            if is_3:
                # slack
                self.stdout.write("#4: Requesting \033[94mSLACK\033[0m...")
                requests = ['home']
                for i, request in enumerate(requests):
                    self.stdout.write("    SLACK: %s / %s (%s)..." % (i + 1, len(requests), request))
                    request = {'qs':request}
                    self.pickle_slack(request)
            else:
                self.stdout.write("#4: Skip SLACK \033[94mhome\033[0m...")


            if is_15:
                # aws init
                self.stdout.write("#1: Requesting \033[94mAWS\033[0m...")
                request = {'qs':'init'}
                aws_init = cache_aws(request)
                pickle.dump(aws_init, open('%s/cache/aws/init.pickle' % MEDIA_ROOT, 'wb'))
                aws_init = simplejson.loads(aws_init)
                self.stdout.write("    AWS \033[94minit\033[0m finished with \033[92mSUCCESS\033[0m.")

                # aws each
                for i, ec2 in enumerate(aws_init['ec2']):
                    self.stdout.write("    AWS \033[94mEC2\033[0m: %s / %s (%s)..." % (i + 1, len(aws_init['ec2']), ec2['id']),)
                    request = {'qs':'cpu', 'tp':'ec2', 'id':ec2['id']}
                    self.pickle_aws(request, ec2['id'])
                    request.update({'qs':'net'})
                    self.pickle_aws(request, ec2['id'])
                    self.stdout.write(" \033[92mSUCCESS\033[0m")

                for i, elb in enumerate(aws_init['elb']):
                    self.stdout.write("    AWS \033[94mELB\033[0m: %s / %s (%s)..." % (i + 1, len(aws_init['elb']), elb['name']),)
                    request = {'qs':'lat', 'tp':'elb', 'id':elb['name']}
                    self.pickle_aws(request, elb['name'])
                    request.update({'qs':'req'})
                    self.pickle_aws(request, elb['name'])
                    self.stdout.write(" \033[92mSUCCESS\033[0m")

                for i, ebs in enumerate(aws_init['ebs']):
                    self.stdout.write("    AWS \033[94mEBS\033[0m: %s / %s (%s)..." % (i + 1, len(aws_init['ebs']), ebs['id']),)
                    request = {'qs':'disk', 'tp':'ebs', 'id':ebs['id']}
                    self.pickle_aws(request, ebs['id'])
                    self.stdout.write(" \033[92mSUCCESS\033[0m")

                # ga init
                self.stdout.write("#2: Requesting \033[94mGA\033[0m...")
                request = {'qs':'init'}
                ga_init = cache_ga(request)
                pickle.dump(ga_init, open('%s/cache/ga/init.pickle' % MEDIA_ROOT, 'wb'))
                ga_init = simplejson.loads(ga_init)
                self.stdout.write("    GA \033[94minit\033[0m finished with \033[92mSUCCESS\033[0m.")

                # ga each
                for i, ga in enumerate(ga_init['projs']):
                    self.stdout.write("    GA \033[94mtracker\033[0m: %s / %s (%s)..." % (i + 1, len(ga_init['projs']), ga['track_id']),)
                    request = {'qs':'sessions', 'id':ga['id'], 'access_token':ga_init['access_token']}
                    self.pickle_ga(request)
                    request.update({'qs':'percentNewSessions'})
                    self.pickle_ga(request)
                    self.stdout.write(" \033[92mSUCCESS\033[0m")

            else:
                self.stdout.write("#1: Skip \033[94mAWS\033[0m...")
                self.stdout.write("#2: Skip \033[94mGA\033[0m...")


            if is_30:
                # git init
                self.stdout.write("#3: Requesting \033[94mGIT\033[0m...")
                request = {'qs':'init'}
                git_init = cache_git(request)
                pickle.dump(git_init, open('%s/cache/git/init.pickle' % MEDIA_ROOT, 'wb'))
                git_init = simplejson.loads(git_init)
                self.stdout.write("    GIT \033[94minit\033[0m finished with \033[92mSUCCESS\033[0m.")

                # git each
                for i, repo in enumerate(git_init['git']):
                    self.stdout.write("    GIT \033[94mrepo\033[0m: %s / %s (%s)..." % (i + 1, len(git_init['git']), repo['name']),)
                    request = {'qs':'num', 'repo':repo['name']}
                    self.pickle_git(request)
                    request.update({'qs':'c'})
                    self.pickle_git(request)
                    request.update({'qs':'ad'})
                    self.pickle_git(request)
                    self.stdout.write(" \033[92mSUCCESS\033[0m")

                # slack
                self.stdout.write("#4: Requesting \033[94mSLACK\033[0m...")
                requests = ['users', 'channels', 'files', 'plot_files', 'plot_msgs']
                for i, request in enumerate(requests):
                    self.stdout.write("    SLACK: %s / %s (%s)..." % (i + 1, len(requests), request),)
                    request = {'qs':request}
                    self.pickle_slack(request)
                    self.stdout.write(" \033[92mSUCCESS\033[0m")

                # dropbox
                self.stdout.write("#5: Requesting \033[94mDROPBOX\033[0m...")
                requests = ['sizes', 'folders', 'history']
                for i, request in enumerate(requests):
                    self.stdout.write("    DROPBOX: %s / %s (%s)..." % (i + 1, len(requests), request),)
                    request = {'qs':request}
                    self.pickle_dropbox(request)
                    self.stdout.write(" \033[92mSUCCESS\033[0m")

                # schedule
                self.stdout.write("#6: Requesting \033[94mSchedule Spreadsheet\033[0m...")
                f_name = '%s/cache/schedule.pickle' % MEDIA_ROOT
                pickle.dump(cache_schedule(), open(f_name + '_tmp', 'wb'))
                subprocess.check_call("mv %s_tmp %s" % (f_name, f_name), shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                self.stdout.write("    Schedule finished with \033[92mSUCCESS\033[0m.")

                # cal
                self.stdout.write("#7: Requesting \033[94mGoogle Calendar\033[0m...")
                f_name = '%s/cache/calendar.pickle' % MEDIA_ROOT
                pickle.dump(cache_cal(), open(f_name + '_tmp', 'wb'))
                subprocess.check_call("mv %s_tmp %s" % (f_name, f_name), shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                self.stdout.write("    Calendar finished with \033[92mSUCCESS\033[0m.")
            else:
                self.stdout.write("#3: Skip \033[94mGIT\033[0m...")
                self.stdout.write("#4: Skip \033[94mSLACK\033[0m...")
                self.stdout.write("#5: Skip \033[94mDROPBOX\033[0m...")
                self.stdout.write("#6: Skip \033[94mSchedule Spreadsheet\033[0m...")
                self.stdout.write("#7: Skip \033[94mGoogle Calendar\033[0m...")
        except:
            err = traceback.format_exc()
            if is_3: var = '3'
            if is_15: var = '15'
            if is_30: var = '30'
            if is_3 and is_15 and is_30: var = ''
            ts = '%s\t\t%s %s\n' % (time.ctime(), sys.argv[0], var)
            open('%s/cache/log_alert_admin.log' % MEDIA_ROOT, 'a').write(ts)
            open('%s/cache/log_cron_cache.log' % MEDIA_ROOT, 'a').write('%s\n%s\n' % (ts, err))
            if IS_SLACK: send_notify_slack(SLACK['ADMIN_NAME'], '', [{"fallback":'ERROR', "mrkdwn_in": ["text"], "color":"danger", "text":'*`ERROR`*: *%s %s* @ _%s_\n>```%s```\n' % (sys.argv[0], var, time.ctime(), err)}])
            self.stdout.write("Finished with \033[41mERROR\033[0m!")
            self.stdout.write("Time elapsed: %.1f s." % (time.time() - t0))
            sys.exit(1)

        self.stdout.write("Finished with \033[92mSUCCESS\033[0m!")
        self.stdout.write("Time elapsed: %.1f s." % (time.time() - t0))
        sys.exit(0)

