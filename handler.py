from urllib.parse import parse_qs
from uuid import uuid1
import json
import time

from boto3.dynamodb import conditions
import boto3
import botocore


DYNAMODB = boto3.resource('dynamodb')

TEMPLATE = """<!doctype html>
<html lang="en">
  <head>
    <title>Demo</title>
    <base href="/dev/">
    <link href="data:image/x-icon;base64,YourBase64StringHere" rel="icon" type="image/x-icon" />

    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
    <link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/4.0.0-beta.2/css/bootstrap.min.css" integrity="sha384-PsH8R72JQ3SOdhVi3uxftmaW6Vc51MKb0q5P2rRUpPvrszuE4W1povHYgTpBfshb" crossorigin="anonymous">
  </head>
  <body>
    <div class="container">
      <nav class="navbar navbar-dark bg-dark">
        <a class="navbar-brand" href=".">Demo App</a>
      </nav>
      {}
    </div>
    <script
      src="https://code.jquery.com/jquery-3.2.1.min.js"
      integrity="sha256-hwg4gsxgFZhOsEEamdOYGBf13FyQuiTwlAQgxVSNgt4="
      crossorigin="anonymous"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jquery-ujs/1.2.2/rails.min.js" integrity="sha256-BbyWhCn0G+F6xbWJ2pcI5LnnpsnpSzyjJNVtl7ABp+M=" crossorigin="anonymous"></script>
  </body>
</html>
"""  # NOQA


def community__form(name_error=''):
    if name_error:
        name_error = '<span class="error">{}</span>'.format(name_error)
    return """<h1>New Community</h1>
<form action="communities" method="post">
  <div class="form-group">
    <label for="community_name">Name</label><br>
    <input class="form-control" type="text" name="community[name]" id="community_name" /></label>{}
  </div>
  <input type="submit" name="commit" value="Create Community" class="btn btn-primary btn-sm" data-disable-with="Create Community" />
</form>
""".format(name_error)  # NOQA


def community_create(event, context):
    data = parse_qs(event['body'])
    name = data.get('community[name]', [''])[0]
    if len(name) < 4:
        return response(
            community__form('is too short (minimum is 4 characters)'))

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
        return response(
            community__form('has already been taken'))
    return redirect('communities/{}'.format(name))


def community_delete(event, context):
    community = event['pathParameters']['name']
    DYNAMODB.Table('communities').delete_item(Key={'title': community})
    submissions_table = DYNAMODB.Table('submissions')
    with submissions_table.batch_writer() as batch:
        for item in submissions_table.scan(
                FilterExpression=conditions.Key('community')
                .eq(community), IndexName='SubmissionCommunityIndex')['Items']:
            batch.delete_item(Key={'id': item['id']})
    return redirect('/dev/')


def community_new(event, context):
    return response(community__form())


def community_show(event, context):
    body = """<h1>{community}</h1>

{listing}

<a class="btn btn-primary" href="submissions/new?community={community}">New Submission</a>
<a class="btn btn-danger" data-confirm="Are you sure?" rel="nofollow" data-method="delete" href="communities/{community}">Delete Community</a>
"""  # NOQA
    community = event['pathParameters']['name']
    table = DYNAMODB.Table('submissions')
    items = table.scan(FilterExpression=conditions.Attr('community')
                       .eq(community))['Items']
    return response(body.format(community=community, listing=listing(sorted(
        items, key=lambda x: -x['createdAt']))))


def json_response(data):
    return {'body': json.dumps(data), 'statusCode': 200}


def listing(data):
    table = """<table class="table">
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
"""

    row = """<tr>
  <td><a href="{url}">{title}</a></td>
  <td>{url}</td>
  <td><a href="communities/{community}">{community}</a></td>
  <td><a class="btn btn-primary btn-sm" href="submissions/{id}">0 comments</a></td>
</tr>
"""  # NOQA
    return table.format(''.join([row.format(**x) for x in data]))


def redirect(path):
    return {'headers': {'Location': path}, 'statusCode': 302}


def response(body=None, status=200):
    data = {'headers': {'Content-Type': 'text/html'}, 'statusCode': status}
    if body is not None:
        data['body'] = TEMPLATE.format(body)
    return data


def root(event, context):
    body = """<h1>Front Page</h1>

{listing}

<a class="btn btn-primary" href="submissions/new">New Submission</a>
<a class="btn btn-primary" href="communities/new">New Community</a>
"""
    table = DYNAMODB.Table('submissions')
    return response(body.format(listing=listing(sorted(
        table.scan()['Items'], key=lambda x: -x['createdAt']))))


def submission__form(community_error='', title_error='', url_error=''):
    if community_error:
        community_error = '<span class="error">{}</span>'.format(
            community_error)
    if title_error:
        title_error = '<span class="error">{}</span>'.format(title_error)
    if url_error:
        url_error = '<span class="error">{}</span>'.format(url_error)

    body = """<h1>New Submission</h1>

<form action="submissions" method="post">
  <div class="form-group">
    <label for="submission_title">Title</label><br>
    <input class="form-control" type="text" name="submission[title]" id="submission_title" />{}
  </div>
  <div class="form-group">
    <label for="submission_url">Url</label><br>
    <input class="form-control" type="text" name="submission[url]" id="submission_url" />{}
  </div>
  <div class="form-group">
    <label for="submission_community">Community</label><br>
    <select class="form-control" name="submission[community]" id="submission_community">{}</select>{}
  </div>
  <input type="submit" name="commit" value="Create Submission" class="btn btn-primary btn-sm" data-disable-with="Create Submission" />
</form>
"""  # NOQA
    table = DYNAMODB.Table('communities')
    communities = sorted(x['title'] for x in table.scan()['Items'])
    options = ''.join(['<option value="{0}">{0}</option>'
                       .format(x) for x in communities])
    return body.format(title_error, url_error, options, community_error)


def submission_create(event, context):
    data = parse_qs(event['body'])
    community = data.get('submission[community]', [''])[0]
    title = data.get('submission[title]', [''])[0]
    url = data.get('submission[url]', [''])[0]

    errors = {}
    if not community:
        errors['community_error'] = 'invalid community'
    if len(title) < 5:
        errors['title_error'] = 'is too short (minimum is 5 characters)'
    if not url.startswith('http'):
        errors['url_error'] = 'is not a valid URL'
    if errors:
        return response(submission__form(**errors))

    table = DYNAMODB.Table('submissions')
    now = int(time.time() * 1000)
    submission_id = str(uuid1())
    item = {'community': community, 'createdAt': now, 'id': submission_id,
            'title': title, 'url': url}

    try:
        table.put_item(ConditionExpression='attribute_not_exists(id)',
                       Item=item)
    except botocore.exceptions.ClientError as exception:
        code = exception.response['Error']['Code']
        if code != 'ConditionalCheckFailedException':
            raise
        return response('{} already exists'.format(title), status=422)
    return redirect('/dev/submissions/{}'.format(submission_id))


def submission_new(event, context):
    return response(submission__form())


def submission_show(event, context):
    body = """<h1>{title} (via <a href="communities/{community}">{community}</a>)</h1>
<p><a href="{url}">{url}</a></p>

<div>
  <a class="btn btn-primary btn-sm" href="comments/new?submission_id={submission_id}">Comment</a>
  <a class="btn btn-danger btn-sm" data-confirm="Are you sure?" data-method="delete" href="submissions/{submission_id}">Delete Submission</a>
</div>
"""  # NOQA
    submission_id = event['pathParameters']['id']
    table = DYNAMODB.Table('submissions')
    submission = table.get_item(Key={'id': submission_id})['Item']
    return response(body.format(
        community=submission['community'], submission_id=submission_id,
        title=submission['title'], url=submission['url']))
