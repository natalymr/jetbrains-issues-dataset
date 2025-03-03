import datetime
import sys
from urllib import parse
import re

import urllib3
from dateutil.relativedelta import relativedelta
import logging

from jetbrains_issues_dataset.youtrack_loader.youtrack import YouTrack

logging.basicConfig(format='%(asctime)s %(message)s', filename='download.log', level=getattr(logging, 'DEBUG'))
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def download_data(youtrack: YouTrack, snapshot_start_time: datetime.datetime, snapshot_end_time: datetime.datetime,
                  query: str, issues_snapshot_file: str = None, activities_snapshot_file: str = None, load_issues=True,
                  load_activities=True, direction='asc', order_by='created', query_type='common'):
    """
    Most parameters have reasonable defaults set below in the CLI argument parser. Minimum working command from CLI if
    working from source:
    PYTHONPATH="$PYTHONPATH:." python ./jetbrains_issues_dataset/idea/download_activities.py --start 2021-01-01 --access-token YOUR_TOKEN
    :param query_type: `common` if timing should be added simply by appending to the end of the query, `formal` if timing should be joined by `and` keyword
    :param youtrack: instance of the YouTrack client
    :param snapshot_start_time: earliest possible issue creation timestamp
    :param snapshot_end_time: latest possible issue creation timestamp
    :param issues_snapshot_file: where to write issues; can be the same as `activities_snapshot_file`
    :param activities_snapshot_file: where to write activity items; can be the same as `issues_snapshot_file`
    :param query: query to filter issues; e.g., use `#IDEA` to obtain all IDEA issues
    :param load_issues: whether to load current issue states
    :param load_activities: whether to load activities
    :param direction: download order: asc (from oldest to newest, default) or desc (from newest to oldest)
    :param order_by: download order criteria: order by when issue was created or by when it was last updated
    """
    if load_issues:
        with open(issues_snapshot_file, 'w', encoding='utf-8') as writer:
            pass
    if load_activities:
        with open(activities_snapshot_file, 'w', encoding='utf-8') as writer:
            pass

    assert snapshot_start_time < snapshot_end_time, f'No issues created after {snapshot_start_time} and before {snapshot_end_time}'
    if direction == 'asc':
        direction_flag = 1
    elif direction == 'desc':
        direction_flag = -1
        snapshot_start_time, snapshot_end_time = snapshot_end_time, snapshot_start_time
    else:
        raise ValueError(f'direction must be either `asc` or `desc`; `{direction}` not recognized')

    assert order_by in ['created', 'updated'], f'We can order by `created` or `updated` timestamp, `{order_by}` not allowed'

    total_issues = 0
    total_activities = 0
    processing_start_time = datetime.datetime.now()
    current_end_date = snapshot_start_time
    while (direction_flag > 0 and snapshot_start_time < snapshot_end_time) or (direction_flag < 0 and snapshot_start_time > snapshot_end_time):
        current_end_date += relativedelta(weeks=1 * direction_flag)
        if (direction_flag > 0 and current_end_date > snapshot_end_time) or (direction_flag < 0 and current_end_date < snapshot_end_time):
            current_end_date = snapshot_end_time

        start = snapshot_start_time.strftime('%Y-%m-%dT%H:%M:%S')
        end = current_end_date.strftime('%Y-%m-%dT%H:%M:%S')

        timed_query = f"{query} {'' if query_type == 'common' else 'and'} {order_by}: {start} .. {end}"
        logging.info(f"Processing from: {start} to: {end}, query: {timed_query}")

        if load_issues:
            issues = youtrack.download_issues(parse.quote_plus(timed_query), issues_snapshot_file, return_ids=True)
            logging.info(f'Loaded {len(issues)} issues')
            total_issues += len(issues)
        else:
            n_issues = 1

        if load_activities and len(issues) > 0:
            # n_activities = youtrack.download_activities(parse.quote_plus(timed_query), activities_snapshot_file)
            n_activities = youtrack.download_activities_per_issue(issues, activities_snapshot_file)
            logging.info(f'Loaded {n_activities} activities')
            total_activities += n_activities
        snapshot_start_time = current_end_date

    logging.info(f'Loaded {total_issues} issues and {total_activities} activity items '
          f'in {str(datetime.datetime.now() - processing_start_time)}')


def cur_time():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')

def filename_from_query(query:str, start:datetime, end:datetime, max_filename_length:int=127):
    filename = re.sub(r'[^A-Za-z]+', '_', query).strip('_')
    dates = f'{start.strftime("%Y%m%d")}_{end.strftime("%Y%m%d")}'
    if max_filename_length:
        filename = filename[:max_filename_length - len(dates)] + '_' + dates
    else:
        filename = f'{filename}_{dates}'
    return filename


def main():
    import argparse
    import os

    parser = argparse.ArgumentParser()

    def youtrack_date(value):
        if isinstance(value, datetime.datetime):
            return value
        try:
            return datetime.datetime.strptime(value, '%Y-%m-%dT%H:%M:%S')
        except ValueError:
            pass
        try:
            return datetime.datetime.strptime(value, '%Y-%m-%d')
        except ValueError:
            raise ValueError(f'value "{value}" cannot be parsed as YouTrack date')

    parser.add_argument('--start',
                        help="earliest issue timestamp in format 1970-01-01T10:00:00 "
                             "(YouTrack search query date format; note the T between date and time)",
                        required=True,
                        type=youtrack_date
                        )
    parser.add_argument('--end',
                        help="latest issue timestamp in format 1970-01-01T10:00:00 "
                             "(YouTrack search query date format; note the T between date and time); "
                             "current time by default",
                        required=False,
                        type=youtrack_date,
                        default=datetime.datetime.now()
                        )
    parser.add_argument('--filename',
                        help='name of the file where to store downloaded data; '
                             'filename.issues.json and filename.activities.json will be created; '
                             'by default, generated from ascii symbols of the query'
                        )
    parser.add_argument('--no-issues', help='if specified, current issue states will not be loaded',
                        action='store_true')
    parser.add_argument('--no-activities', help='if specified, activities related to the issue will not be loaded',
                        action='store_true')
    parser.add_argument('--direction', help='download order: asc (from oldest to newest, default) or desc (from newest to oldest)',
                        choices=['asc', 'desc'], default='asc')
    parser.add_argument('--order-by',
                        help='download order criteria: order by when issue was created or by when it was last updated',
                        choices=['created', 'updated'], default='created')
    parser.add_argument('--server-address',
                        help='where to download issues from',
                        default='https://youtrack-staging.labs.intellij.net/'
                        )
    parser.add_argument('--access-token',
                        help='access token to the server, either string or path to file with token',
                        required=True
                        )
    parser.add_argument('--query-type',
                        help='query grammar used, either `common` (default) or `formal`; '
                        'if `common`, additional query parameters are joined by simply appending to the query string '
                             '(example: `your_query created: 2021-01-01 .. 2021-01-02`), '
                             'if `formal`, additional query parameters are joined by `and` operator '
                             '(example: `your_query and created: 2021-01-01 .. 2021-01-02`)',
                        choices=['common', 'formal'], default='common')
    parser.add_argument('--query',
                        help='query to filter issues; default is #IDEA',
                        nargs='*',
                        default=['#IDEA']
                        )

    args = parser.parse_args()
    print(args)

    if os.path.exists(args.access_token):
        access_token = open(args.access_token, 'r').read().strip()
    else:
        access_token = args.access_token
    youtrack = YouTrack(args.server_address, access_token)

    query = ' '.join(args.query)

    if args.filename:
        filename = args.filename
    else:
        filename = filename_from_query(query, args.start, args.end)
    root, ext = os.path.splitext(filename)
    if not ext:
        ext = '.json'
    issues_snapshot_file = f'{root}.issues{ext}'
    activities_snapshot_file = f'{root}.activities{ext}'

    download_data(youtrack=youtrack, snapshot_start_time=args.start, snapshot_end_time=args.end, query=query,
                  issues_snapshot_file=issues_snapshot_file, activities_snapshot_file=activities_snapshot_file,
                  load_issues=not args.no_issues, load_activities=not args.no_activities, direction=args.direction,
                  order_by=args.order_by, query_type=args.query_type)


if __name__ == '__main__':
    main()
