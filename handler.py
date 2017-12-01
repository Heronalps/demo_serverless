from urllib.parse import parse_qs
from uuid import uuid1
import json
import time

import boto3
import botocore


DYNAMODB = boto3.resource('dynamodb')

TEMPLATE = """<!DOCTYPE html>
<html>
<head>
  <title>Demo</title>
  <base href="/dev/">
  <link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.2/css/bootstrap.min.css">
  <link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.2/css/bootstrap-theme.min.css">
</head>
<body>
  <div class="container">
    <nav class="navbar navbar-default">
      <a class="navbar-brand" href=".">Demo App</a>
    </nav>
    {}
  </div>

  <script src="https://ajax.googleapis.com/ajax/libs/jquery/1.11.2/jquery.min.js"></script>
  <script src="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.2/js/bootstrap.min.js"></script>
</body>
</html>
"""  # NOQA


def json_response(data):
    return {'body': json.dumps(data), 'statusCode': 200}


def response(body=None, status=200):
    data = {'headers': {'Content-Type': 'text/html'}, 'statusCode': status}
    if body is not None:
        data['body'] = TEMPLATE.format(body)
    return data


def redirect(path):
    return {'headers': {'Location': path}, 'statusCode': 302}


def root(event, context):
    body = """<h3>Submissions</h3>

<table class="table">
  <thead>
    <tr>
      <th>Title</th>
      <th>Url</th>
      <th>Community</th>
      <th colspan="3"></th>
    </tr>
  </thead>

  <tbody>{}</tbody>
</table>

<br>
<a class="btn btn-primary" href="submissions/new">New Submission</a>
<a class="btn btn-primary" href="communities/new">New Community</a>
"""

    row = """<tr>
  <td><a href="{url}">{title}</a></td>
  <td>{url}</td>
  <td>{community}</td>
  <td><a class="btn btn-primary btn-xs" href="submissions/{id}">0 comments</a></td>
</tr>
"""  # NOQA

    table = DYNAMODB.Table('submissions')
    submissions = [row.format(**x) for x in sorted(
        table.scan()['Items'], key=lambda x: -x['createdAt'])]
    return response(body.format(''.join(submissions)))


def community_create(event, context):
    data = parse_qs(event['body'])
    name = data['community[name]'][0]

    table = DYNAMODB.Table('communities')
    now = int(time.time() * 1000)
    item = {'createdAt': now, 'title': name}
    try:
        table.put_item(ConditionExpression='attribute_not_exists(title)',
                       Item=item)
    except botocore.exceptions.ClientError as exception:
        code = exception.response['Error']['Code']
        if code != 'ConditionalCheckFailedException':
            raise
        return response('{} already exists'.format(name))
    return redirect('communities')


def community_delete(event, context):
    return response(status=204)


def community_list(event, context):
    table = DYNAMODB.Table('communities')
    return json_response(sorted(x['title'] for x in table.scan()['Items']))


def community_new(event, context):
    body = """<h1>New Community</h1>

<form action="communities" method="post">
  <div class="field">
    <label for="community_name">Name</label><br>
    <input class="form-control" type="text" name="community[name]" id="community_name" /></label>
  </div>
  <div class="actions">
    <input type="submit" name="commit" value="Create Community" class="btn btn-primary" />
  </div>
</form>

<a href="communities">Back</a>
"""  # NOQA
    return response(body)


def submission_new(event, context):
    body = """<h1>New Submission</h1>

<form action="submissions" method="post">
  <div class="field">
    <label for="submission_title">Title</label><br>
    <input class="form-control" type="text" name="submission[title]" id="submission_title" />
  </div>
  <div class="field">
    <label for="submission_url">Url</label><br>
    <input class="form-control" type="text" name="submission[url]" id="submission_url" />
  </div>
  <div class="field">
    <label for="submission_community_id">Community</label><br>
    <select class="form-control" name="submission[community_id]" id="submission_community_id">{}</select>
  </div>
  <div class="actions">
    <input type="submit" name="commit" value="Create Submission" class="btn btn-primary" />
  </div>
</form>
"""  # NOQA
    table = DYNAMODB.Table('communities')
    communities = sorted(x['title'] for x in table.scan()['Items'])
    options = ''.join(['<option value="{0}">{0}</option>'
                       .format(x) for x in communities])
    return response(body.format(options))


def submission_create(event, context):
    data = parse_qs(event['body'])
    community = data['submission[community_id]'][0]
    title = data['submission[title]'][0]
    url = data['submission[url]'][0]

    table = DYNAMODB.Table('submissions')
    now = int(time.time() * 1000)
    item = {'community': community, 'createdAt': now, 'id': str(uuid1()),
            'title': title, 'url': url}

    try:
        table.put_item(ConditionExpression='attribute_not_exists(id)',
                       Item=item)
    except botocore.exceptions.ClientError as exception:
        code = exception.response['Error']['Code']
        if code != 'ConditionalCheckFailedException':
            raise
        return response('{} already exists'.format(title))
    return redirect('.')
