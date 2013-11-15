from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Max, Min
from django.shortcuts import render

import datetime

from niko.models import Poll, Vote

def poll(request, slug, year=None, month=None, day=None, error=None, success=None):
	"""Show details of a specific poll."""
	context = {
		'error'   : error,
		'hostname': request.get_host(),
		'success' : success,
		'Vote'    : Vote
	}

	# Find related poll
	try:
		poll = Poll.objects.get(slug = slug)
		context['poll'] = poll
	except ObjectDoesNotExist:
		no_poll = 'No poll for {}'.format(slug.title())
		context['error'] = error + no_poll if error  else no_poll
		return render(request, 'poll.html', context)

	votes = None
	if day and month and year:
		givendate = datetime.date(int(year), int(month), int(day))
		votes = Vote.objects.filter(poll__id=poll.id).filter(
			pub_date__gte = givendate).order_by('-pub_date')
		context['day']   = day
		context['month'] = month
		context['year']  = year
	else:
		votes = Vote.objects.filter(poll__id=poll.id).order_by(
			'-pub_date')
	context['votes'] = votes
	
	# Compute average mood
	votes_count = votes.count()
	context['votes_count'] = votes_count
	votes_kinds = { 'bads': Vote.BAD , 'oks' : Vote.OK,
		'greats' : Vote.GREAT }
	if votes_count > 0:
		for varname, votetype in votes_kinds.iteritems():
			# Compute average safely
			count_key = varname + "_count"
			percentage_key = varname + "_percentage"
			context[count_key] = votes.filter( mood = votetype ).count()
			if context[count_key] > 0:
				context[percentage_key] = 100.0 * \
					(float(context[count_key]) / float(votes_count))
			else:
				context[percentage_key] = 0
	else:
		for varname, _ in votes_kinds.iteritems():
			context[varname + "_count"] = 0
			context[varname + "_percentage"] = 0

	#
	# Change over time
	#

	# Define date shown in bar chart
	context['linechart'] = {}
	dates = votes.aggregate(Max('pub_date'), Min('pub_date'))
	startdate = dates['pub_date__min']
	enddate   = dates['pub_date__max']
	if startdate == enddate:
		context['linechart']['labels'] = [ startdate ]
		context['linechart']['values'] = {}
		for varname, votetype in votes_kinds.iteritems():
			context['linechart']['values'][varname]=[votes.filter(mood = votetype).\
				count()]
	else:
		timestep = (enddate - startdate) / 3
		dates = [startdate, startdate + timestep, startdate + 2 * timestep, enddate]
		context['linechart']['labels'] = dates
		context['linechart']['values'] = {}
		for adate in dates:
			for varname, votetype in votes_kinds.iteritems():
				count =votes.filter(mood=votetype, pub_date__lte=adate).count()
				if not varname in context['linechart']['values']:
					context['linechart']['values'][varname] = []
				context['linechart']['values'][varname].append( count )

	return render(request, 'poll.html', context)

def polls(request):
	polls = Poll.objects.all().order_by('-pub_date')
	return render(request, 'polls.html', { 'polls' : polls } )

def save(request, slug, mood):
	"""Saves a vote to database."""
	# Find related poll
	context = { 'Vote' : Vote }
	try:
		a_poll = Poll.objects.get(slug = slug)
		context['poll'] = a_poll
	except ObjectDoesNotExist:
		context['error'] = 'No poll for {}'.format(slug.title())
		return render(request, 'vote.html',context)

	# TODO: Create object with current date in database
	today = datetime.date.today()
	error = None
	success = None
	if not mood in [Vote.BAD, Vote.OK, Vote.GREAT]:
		error = 'I do not know this kind of vote.'
	else:
		currentip = get_client_ip(request)
		yesterday = today - datetime.timedelta( days = 1 )
		today_s_votes = Vote.objects.filter(poll__id=a_poll.id).filter(
			ip = currentip,pub_date__gt = yesterday).count() 
		if today_s_votes > 0:
			error = '{} already voted today.'.format(currentip)
		else:
			Vote.objects.create(ip = currentip, mood = mood,
				pub_date = today, poll_id = a_poll.id)
			success = 'Vote saved.'
	return poll(request, slug, error = error, success = success)

def vote(request, slug):
	context = {'Vote': Vote}
	try:
		context['poll'] = Poll.objects.get(slug = slug)
	except ObjectDoesNotExist:
		context['error'] = 'No poll for {}'.format(slug.title())
	return render(request, 'vote.html', context)

# Utilities
def get_client_ip(request):
	x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
	if x_forwarded_for:
		ip = x_forwarded_for.split(',')[0]
	else:
		ip = request.META.get('REMOTE_ADDR')
	return ip
