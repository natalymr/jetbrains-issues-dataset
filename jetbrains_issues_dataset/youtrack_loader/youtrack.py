import datetime
import json
import logging
import time
from typing import Union, List

import requests


class IssueWithProblemDownloader(Exception):
    def __init__(self, message, issue):
        self.message = message
        self.issue = issue

    def __str__(self):
        return self.message + f"for issue: {self.issue}"


ISSUES_QUERY = "issues?query={query}&fields=" \
               "id,idReadable,summary,description," \
               "project(shortName),created,resolved,reporter(login,fullName,ringId),commentsCount," \
               "customFields(id,name,value(id,name,login,ringId))," \
               "comments(id,created,text,author(login,name,ringId))," \
               "links(direction,linkType(name,sourceToTarget,targetToSource,directed,aggregation),issues(id,idReadable))," \
               "tags(id,name)" \
               "&$skip={skip}&$top={top}"

ACTIVITIES_QUERY = "activities/?issueQuery={}&categories=CommentsCategory,AttachmentsCategory,AttachmentRenameCategory," \
                   "CustomFieldCategory,DescriptionCategory,IssueCreatedCategory,IssueResolvedCategory,LinksCategory," \
                   "ProjectCategory,IssueVisibilityCategory,SprintCategory,SummaryCategory,TagsCategory" \
                   "&fields=id,idReadable,timestamp,targetMember,target(id," \
                   "reporter(login,name,ringId),created,idReadable,text,issue(id),customFields(id,name,value(id,name,login,ringId)))," \
                   "memberName,added(id,login,name,text),removed(id,login,name,text)&$skip={}&$top={}"

ACTIVITIES_PER_ISSUE_QUERY = "issues/{issue_id}/activities?categories=CommentsCategory,CommentTextCategory," \
                 "AttachmentsCategory,AttachmentRenameCategory,CustomFieldCategory,DescriptionCategory," \
                 "IssueCreatedCategory,IssueResolvedCategory,LinksCategory,ProjectCategory,IssueVisibilityCategory," \
                 "SprintCategory,SummaryCategory,TagsCategory,CommentReactionCategory," \
                 "VotersCategory,VcsChangeCategory" \
                 "&fields=id,idReadable,timestamp,targetMember(id)," \
                 "target(id,issue(id),name,project(id,shortName),branch,date," \
                    "reporter(id,login,name,fullName,ringId,guest,email)," \
                 "idReadable,text,issue(id)," \
                 "votes," \
                 "visibility(id,permittedGroups(id,name,ringId),permittedUsers(id,fullName,ringId,email))," \
                 "created,resolved,customFields(id,name,value(id,name,login,ringId)))," \
                 "memberName," \
                 "category(id)," \
                 "field(id,name)," \
                 "added(id,name,login,ringId,email,value(id,name,login,ringId),reaction," \
                    "text,bundle(id,name),project(id,shortName),numberInProject," \
                    "state,files,fetched,version,urls,processors(id,project(id,shortName),server(id))," \
                    "author(id,login,name,fullName,ringId,guest,email))," \
                 "removed(id,name,login,ringId,email,value(id,name,login,ringId),reaction," \
                    "text,bundle(id,name),project(id,shortName),numberInProject," \
                    "state,files,fetched,version,urls,processors(id,project(id,shortName),server(id))," \
                    "author(id,login,name,fullName,ringId,guest,email))," \
                 "author(id,login,name,fullName,ringId,guest,email)" \
                 "&$skip={skip}&$top={top}"



ALL_CATEGORIES = "CommentsCategory,CommentTextCategory," \
                 "AttachmentsCategory,AttachmentRenameCategory,CustomFieldCategory,DescriptionCategory," \
                 "IssueCreatedCategory,IssueResolvedCategory,LinksCategory,ProjectCategory,IssueVisibilityCategory," \
                 "SprintCategory,SummaryCategory,TagsCategory,CommentReactionCategory," \
                 "VotersCategory,VcsChangeCategory"

ACTIVITIES_PER_ISSUE_QUERY = "issues/{issue_id}/activities?categories={categories}" \
                 "&fields=id,idReadable,timestamp,targetMember(id)," \
                 "target(id,issue(id),name,project(id,shortName),branch,date," \
                    "reporter(id,login,name,fullName,ringId,guest,email)," \
                 "idReadable,text,issue(id)," \
                 "votes," \
                 "visibility(id,permittedGroups(id,name,ringId),permittedUsers(id,fullName,ringId,email))," \
                 "created,resolved,customFields(id,name,value(id,name,login,ringId)))," \
                 "memberName," \
                 "category(id)," \
                 "field(id,name)," \
                 "added(id,name,login,ringId,email,value(id,name,login,ringId),reaction," \
                    "text,bundle(id,name),project(id,shortName),numberInProject," \
                    "state,files,fetched,version,urls,processors(id,project(id,shortName),server(id))," \
                    "author(id,login,name,fullName,ringId,guest,email))," \
                 "removed(id,name,login,ringId,email,value(id,name,login,ringId),reaction," \
                    "text,bundle(id,name),project(id,shortName),numberInProject," \
                    "state,files,fetched,version,urls,processors(id,project(id,shortName),server(id))," \
                    "author(id,login,name,fullName,ringId,guest,email))," \
                 "author(id,login,name,fullName,ringId,guest,email)" \
                 "&$skip={skip}&$top={top}"


class YouTrack:
    def __init__(self, url, token, page_size=1000):
        self.url = url
        self.new_api_url = url + "api/"
        self.old_api_url = url + "rest/"
        self.headers = {
            "Accept": "application/json"
        }
        if token is not None:
            self.headers["Authorization"] = "Bearer {}".format(token)

        self.page_size = page_size
        self.activity_list_url = self.new_api_url + ACTIVITIES_QUERY
        self.issue_list_url = self.new_api_url + ISSUES_QUERY
        self.activities_per_issue_url = self.new_api_url + ACTIVITIES_PER_ISSUE_QUERY

    def download_activities_per_issue(self, issue_ids, file_path, categories=None, no_write_to_file=False):
        total_activities = 0
        downloaded_activies = []
        for i, issue_id in enumerate(issue_ids):
            skip = 0
            while True:
                needed_categories = ALL_CATEGORIES if categories is None else categories
                request_url = self.activities_per_issue_url.format(issue_id=issue_id, categories=needed_categories,
                                                                   skip=skip, top=self.page_size)
                activity_list = None
                attempt = 1
                while attempt < 5:
                    try:
                        response = requests.get(request_url, headers=self.headers, verify=False)
                        activity_list = response.json()
                        break
                    except Exception as e:
                        logging.exception(e)
                        time.sleep(3)
                    attempt += 1

                if activity_list is None:
                    raise Exception("Failed to retrieve activities")

                try:
                    self.check_response(activity_list)
                except Exception:
                    raise IssueWithProblemDownloader('downloading failed ', issue_id)

                now = round(datetime.datetime.now().timestamp() * 1000)

                for activity in activity_list:
                    activity['element_type'] = 'activity'
                    activity['issue_id'] = issue_id
                    activity['download_timestamp'] = now

                if no_write_to_file:
                    downloaded_activies.extend(activity_list)
                else:
                    with open(file_path, 'a+', encoding='utf-8') as writer:
                        for activity in activity_list:
                            line = json.dumps(activity, ensure_ascii=False)
                            line = line.replace('\u0000', '')
                            line = (line + '\n').encode('utf-8', 'replace').decode('utf-8', 'replace')
                            writer.write(line)

                skip += len(activity_list)
                total_activities += len(activity_list)

                if len(activity_list) < self.page_size:
                    break

        return downloaded_activies if no_write_to_file else total_activities

    def download_issues(self, query, file_path, return_ids=False) -> Union[int, List[str]]:
        skip = 0
        all_issues = []
        while True:
            response = requests.get(self.issue_list_url.format(query=query, skip=skip, top=self.page_size),
                                    headers=self.headers,
                                    verify=False)
            loaded_issues = response.json()
            self.check_response(loaded_issues)

            if len(loaded_issues) == 0:
                break

            now = round(datetime.datetime.now().timestamp() * 1000)
            for issue in all_issues:
                issue['downloadTimestamp'] = now
            skip += len(loaded_issues)
            all_issues += loaded_issues

        with open(file_path, 'a+', encoding='utf-8') as writer:
            for issue in all_issues:
                issue['element_type'] = 'issue'
                line = json.dumps(issue, ensure_ascii=False).encode('utf-8', 'replace').decode('utf-8')
                try:
                    writer.write(line + '\n')
                except Exception as e:
                    logging.exception(issue['id'])
                    raise e

        if return_ids:
            return [issue['id'] for issue in all_issues]
        else:
            return len(all_issues)

    @staticmethod
    def check_response(json_response):
        if 'error' in json_response:
            print(json_response)
            raise Exception(json_response['error'])
        # print('read {} items'.format(len(json_response)))
