#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import unittest

from pymisp import ExpandedPyMISP, MISPEvent, MISPOrganisation, MISPUser, Distribution, ThreatLevel, Analysis
from datetime import datetime, timedelta, date
from io import BytesIO

import time

try:
    from keys import url, key
except ImportError as e:
    print(e)
    url = 'http://localhost:8080'
    key = 'fk5BodCZw8owbscW8pQ4ykMASLeJ4NYhuAbshNjo'

from uuid import uuid4

travis_run = True


class TestComprehensive(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.maxDiff = None
        # Connect as admin
        cls.admin_misp_connector = ExpandedPyMISP(url, key, debug=False)
        # Creates an org
        org = cls.admin_misp_connector.add_organisation(name='Test Org')
        cls.test_org = MISPOrganisation()
        cls.test_org.from_dict(**org)
        # Creates a user
        usr = cls.admin_misp_connector.add_user(email='testusr@user.local', org_id=cls.test_org.id, role_id=3)
        cls.test_usr = MISPUser()
        cls.test_usr.from_dict(**usr)
        cls.user_misp_connector = ExpandedPyMISP(url, cls.test_usr.authkey)
        # Creates a publisher
        pub = cls.admin_misp_connector.add_user(email='testpub@user.local', org_id=cls.test_org.id, role_id=4)
        cls.test_pub = MISPUser()
        cls.test_pub.from_dict(**pub)
        cls.pub_misp_connector = ExpandedPyMISP(url, cls.test_pub.authkey)

    @classmethod
    def tearDownClass(cls):
        # Delete publisher
        cls.admin_misp_connector.delete_user(user_id=cls.test_pub.id)
        # Delete user
        cls.admin_misp_connector.delete_user(user_id=cls.test_usr.id)
        # Delete org
        cls.admin_misp_connector.delete_organisation(org_id=cls.test_org.id)

    def create_simple_event(self, force_timestamps=False):
        mispevent = MISPEvent(force_timestamps=force_timestamps)
        mispevent.info = 'This is a super simple test'
        mispevent.distribution = Distribution.your_organisation_only
        mispevent.threat_level_id = ThreatLevel.low
        mispevent.analysis = Analysis.completed
        mispevent.add_attribute('text', str(uuid4()))
        return mispevent

    def environment(self):
        first_event = MISPEvent()
        first_event.info = 'First event - org only - low - completed'
        first_event.distribution = Distribution.your_organisation_only
        first_event.threat_level_id = ThreatLevel.low
        first_event.analysis = Analysis.completed
        first_event.set_date("2017-12-31")
        first_event.add_attribute('text', str(uuid4()))
        first_event.attributes[0].add_tag('admin_only')
        first_event.attributes[0].add_tag('tlp:white___test')
        first_event.add_attribute('text', str(uuid4()))
        first_event.attributes[1].add_tag('unique___test')

        second_event = MISPEvent()
        second_event.info = 'Second event - org only - medium - ongoing'
        second_event.distribution = Distribution.your_organisation_only
        second_event.threat_level_id = ThreatLevel.medium
        second_event.analysis = Analysis.ongoing
        second_event.set_date("Aug 18 2018")
        second_event.add_attribute('text', str(uuid4()))
        second_event.attributes[0].add_tag('tlp:white___test')
        second_event.add_attribute('ip-dst', '1.1.1.1')
        # Same value as in first event.
        second_event.add_attribute('text', first_event.attributes[0].value)

        third_event = MISPEvent()
        third_event.info = 'Third event - all orgs - high - initial'
        third_event.distribution = Distribution.all_communities
        third_event.threat_level_id = ThreatLevel.high
        third_event.analysis = Analysis.initial
        third_event.set_date("Jun 25 2018")
        third_event.add_tag('tlp:white___test')
        third_event.add_attribute('text', str(uuid4()))
        third_event.attributes[0].add_tag('tlp:amber___test')
        third_event.attributes[0].add_tag('foo_double___test')
        third_event.add_attribute('ip-src', '8.8.8.8')
        third_event.attributes[1].add_tag('tlp:amber___test')
        third_event.add_attribute('ip-dst', '9.9.9.9')

        # Create first and third event as admin
        # usr won't be able to see the first one
        first = self.admin_misp_connector.add_event(first_event)
        third = self.admin_misp_connector.add_event(third_event)
        # Create second event as user
        second = self.user_misp_connector.add_event(second_event)
        return first, second, third

    def test_search_value_event(self):
        '''Search a value on the event controller
        * Test ACL admin user vs normal user in an other org
        * Make sure we have one match
        '''
        try:
            first, second, third = self.environment()
            # Search as admin
            events = self.admin_misp_connector.search(value=first.attributes[0].value, pythonify=True)
            self.assertEqual(len(events), 2)
            for e in events:
                self.assertIn(e.id, [first.id, second.id])
            # Search as user
            events = self.user_misp_connector.search(value=first.attributes[0].value, pythonify=True)
            self.assertEqual(len(events), 1)
            for e in events:
                self.assertIn(e.id, [second.id])
            # Non-existing value
            events = self.user_misp_connector.search(value=str(uuid4()), pythonify=True)
            self.assertEqual(events, [])
        finally:
            # Delete events
            self.admin_misp_connector.delete_event(first.id)
            self.admin_misp_connector.delete_event(second.id)
            self.admin_misp_connector.delete_event(third.id)

    def test_search_value_attribute(self):
        '''Search value in attributes controller'''
        try:
            first, second, third = self.environment()
            # Search as admin
            attributes = self.admin_misp_connector.search(controller='attributes', value=first.attributes[0].value, pythonify=True)
            self.assertEqual(len(attributes), 2)
            for a in attributes:
                self.assertIn(a.event_id, [first.id, second.id])
            # Search as user
            attributes = self.user_misp_connector.search(controller='attributes', value=first.attributes[0].value, pythonify=True)
            self.assertEqual(len(attributes), 1)
            for a in attributes:
                self.assertIn(a.event_id, [second.id])
            # Non-existing value
            attributes = self.user_misp_connector.search(controller='attributes', value=str(uuid4()), pythonify=True)
            self.assertEqual(attributes, [])
        finally:
            # Delete event
            self.admin_misp_connector.delete_event(first.id)
            self.admin_misp_connector.delete_event(second.id)
            self.admin_misp_connector.delete_event(third.id)

    def test_search_type_event(self):
        '''Search multiple events, search events containing attributes with specific types'''
        try:
            first, second, third = self.environment()
            # Search as admin
            events = self.admin_misp_connector.search(timestamp=first.timestamp.timestamp(), pythonify=True)
            self.assertEqual(len(events), 3)
            for e in events:
                self.assertIn(e.id, [first.id, second.id, third.id])
            attributes_types_search = self.admin_misp_connector.build_complex_query(or_parameters=['ip-src', 'ip-dst'])
            events = self.admin_misp_connector.search(timestamp=first.timestamp.timestamp(),
                                                      type_attribute=attributes_types_search, pythonify=True)
            self.assertEqual(len(events), 2)
            for e in events:
                self.assertIn(e.id, [second.id, third.id])
        finally:
            # Delete event
            self.admin_misp_connector.delete_event(first.id)
            self.admin_misp_connector.delete_event(second.id)
            self.admin_misp_connector.delete_event(third.id)

    def test_search_type_attribute(self):
        '''Search multiple attributes, search attributes with specific types'''
        try:
            first, second, third = self.environment()
            # Search as admin
            attributes = self.admin_misp_connector.search(controller='attributes',
                                                          timestamp=first.timestamp.timestamp(), pythonify=True)
            self.assertEqual(len(attributes), 8)
            for a in attributes:
                self.assertIn(a.event_id, [first.id, second.id, third.id])
            # Search as user
            attributes_types_search = self.admin_misp_connector.build_complex_query(or_parameters=['ip-src', 'ip-dst'])
            attributes = self.admin_misp_connector.search(controller='attributes',
                                                          timestamp=first.timestamp.timestamp(),
                                                          type_attribute=attributes_types_search, pythonify=True)
            self.assertEqual(len(attributes), 3)
            for a in attributes:
                self.assertIn(a.event_id, [second.id, third.id])
        finally:
            # Delete event
            self.admin_misp_connector.delete_event(first.id)
            self.admin_misp_connector.delete_event(second.id)
            self.admin_misp_connector.delete_event(third.id)

    def test_search_tag_event(self):
        '''Search Tags at events level'''
        try:
            first, second, third = self.environment()
            # Search as admin
            events = self.admin_misp_connector.search(tags='tlp:white___test', pythonify=True)
            self.assertEqual(len(events), 3)
            for e in events:
                self.assertIn(e.id, [first.id, second.id, third.id])
            events = self.admin_misp_connector.search(tags='tlp:amber___test', pythonify=True)
            self.assertEqual(len(events), 1)
            for e in events:
                self.assertIn(e.id, [third.id])
            events = self.admin_misp_connector.search(tags='admin_only', pythonify=True)
            self.assertEqual(len(events), 1)
            for e in events:
                self.assertIn(e.id, [first.id])
            # Search as user
            events = self.user_misp_connector.search(tags='tlp:white___test', pythonify=True)
            self.assertEqual(len(events), 2)
            for e in events:
                self.assertIn(e.id, [second.id, third.id])
            events = self.user_misp_connector.search(tags='tlp:amber___test', pythonify=True)
            self.assertEqual(len(events), 1)
            for e in events:
                self.assertIn(e.id, [third.id])
            events = self.user_misp_connector.search(tags='admin_only', pythonify=True)
            self.assertEqual(events, [])
        finally:
            # Delete event
            self.admin_misp_connector.delete_event(first.id)
            self.admin_misp_connector.delete_event(second.id)
            self.admin_misp_connector.delete_event(third.id)

    def test_search_tag_attribute(self):
        '''Search Tags at attributes level'''
        try:
            first, second, third = self.environment()
            # Search as admin
            attributes = self.admin_misp_connector.search(controller='attributes', tags='tlp:white___test', pythonify=True)
            self.assertEqual(len(attributes), 5)
            attributes = self.admin_misp_connector.search(controller='attributes', tags='tlp:amber___test', pythonify=True)
            self.assertEqual(len(attributes), 2)
            attributes = self.admin_misp_connector.search(tags='admin_only', pythonify=True)
            self.assertEqual(len(attributes), 1)
            # Search as user
            attributes = self.user_misp_connector.search(controller='attributes', tags='tlp:white___test', pythonify=True)
            self.assertEqual(len(attributes), 4)
            attributes = self.user_misp_connector.search(controller='attributes', tags='tlp:amber___test', pythonify=True)
            self.assertEqual(len(attributes), 2)
            attributes = self.user_misp_connector.search(tags='admin_only', pythonify=True)
            self.assertEqual(attributes, [])
        finally:
            # Delete event
            self.admin_misp_connector.delete_event(first.id)
            self.admin_misp_connector.delete_event(second.id)
            self.admin_misp_connector.delete_event(third.id)

    def test_search_tag_advanced_event(self):
        '''Advanced search Tags at events level'''
        try:
            first, second, third = self.environment()
            complex_query = self.admin_misp_connector.build_complex_query(or_parameters=['tlp:white___test'],
                                                                          not_parameters=['tlp:amber___test',
                                                                                          'foo_double___test'])
            events = self.admin_misp_connector.search(tags=complex_query, pythonify=True)
            self.assertEqual(len(events), 3)
            for e in events:
                self.assertIn(e.id, [first.id, second.id, third.id])
                for a in e.attributes:
                    self.assertEqual([t for t in a.tags if t.name == 'tlp:amber___test'], [])
                for a in e.attributes:
                    self.assertEqual([t for t in a.tags if t.name == 'foo_double___test'], [])

            complex_query = self.admin_misp_connector.build_complex_query(or_parameters=['unique___test'],
                                                                          not_parameters=['tlp:white___test'])
            events = self.admin_misp_connector.search(tags=complex_query, pythonify=True)
            self.assertEqual(len(events), 1)
            for e in events:
                self.assertIn(e.id, [first.id, second.id])
                for a in e.attributes:
                    self.assertEqual([t for t in a.tags if t.name == 'tlp:white___test'], [])
        finally:
            # Delete event
            self.admin_misp_connector.delete_event(first.id)
            self.admin_misp_connector.delete_event(second.id)
            self.admin_misp_connector.delete_event(third.id)

    def test_search_tag_advanced_attributes(self):
        '''Advanced search Tags at attributes level'''
        try:
            first, second, third = self.environment()
            complex_query = self.admin_misp_connector.build_complex_query(or_parameters=['tlp:white___test'],
                                                                          not_parameters=['tlp:amber___test',
                                                                                          'foo_double___test'])
            attributes = self.admin_misp_connector.search(controller='attributes', tags=complex_query, pythonify=True)
            self.assertEqual(len(attributes), 3)
            for a in attributes:
                self.assertEqual([t for t in a.tags if t.name == 'tlp:amber___test'], [])
            for a in attributes:
                self.assertEqual([t for t in a.tags if t.name == 'foo_double___test'], [])
        finally:
            # Delete event
            self.admin_misp_connector.delete_event(first.id)
            self.admin_misp_connector.delete_event(second.id)
            self.admin_misp_connector.delete_event(third.id)

    def test_search_timestamp_event(self):
        '''Search specific update timestamps at events level'''
        # Creating event 1 - timestamp 5 min ago
        first = self.create_simple_event(force_timestamps=True)
        event_creation_timestamp_first = datetime.now() - timedelta(minutes=5)
        first.timestamp = event_creation_timestamp_first
        # Creating event 2 - timestamp 2 min ago
        second = self.create_simple_event(force_timestamps=True)
        event_creation_timestamp_second = datetime.now() - timedelta(minutes=2)
        second.timestamp = event_creation_timestamp_second
        try:
            first = self.user_misp_connector.add_event(first)
            second = self.user_misp_connector.add_event(second)
            # Search as user
            # # Test - last 4 min
            events = self.user_misp_connector.search(timestamp='4m', pythonify=True)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].id, second.id)
            self.assertEqual(events[0].timestamp.timestamp(), int(event_creation_timestamp_second.timestamp()))

            # # Test timestamp of 2nd event
            events = self.user_misp_connector.search(timestamp=event_creation_timestamp_second.timestamp(), pythonify=True)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].id, second.id)
            self.assertEqual(events[0].timestamp.timestamp(), int(event_creation_timestamp_second.timestamp()))

            # # Test interval -6 min -> -4 min
            events = self.user_misp_connector.search(timestamp=['6m', '4m'], pythonify=True)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].id, first.id)
            self.assertEqual(events[0].timestamp.timestamp(), int(event_creation_timestamp_first.timestamp()))
        finally:
            # Delete event
            self.admin_misp_connector.delete_event(first.id)
            self.admin_misp_connector.delete_event(second.id)

    def test_search_timestamp_attribute(self):
        '''Search specific update timestamps at attributes level'''
        # Creating event 1 - timestamp 5 min ago
        first = self.create_simple_event(force_timestamps=True)
        event_creation_timestamp_first = datetime.now() - timedelta(minutes=5)
        first.timestamp = event_creation_timestamp_first
        first.attributes[0].timestamp = event_creation_timestamp_first
        # Creating event 2 - timestamp 2 min ago
        second = self.create_simple_event(force_timestamps=True)
        event_creation_timestamp_second = datetime.now() - timedelta(minutes=2)
        second.timestamp = event_creation_timestamp_second
        second.attributes[0].timestamp = event_creation_timestamp_second
        try:
            first = self.user_misp_connector.add_event(first)
            second = self.user_misp_connector.add_event(second)
            # Search as user
            # # Test - last 4 min
            attributes = self.user_misp_connector.search(controller='attributes', timestamp='4m', pythonify=True)
            self.assertEqual(len(attributes), 1)
            self.assertEqual(attributes[0].event_id, second.id)
            self.assertEqual(attributes[0].timestamp.timestamp(), int(event_creation_timestamp_second.timestamp()))

            # # Test timestamp of 2nd event
            attributes = self.user_misp_connector.search(controller='attributes', timestamp=event_creation_timestamp_second.timestamp(), pythonify=True)
            self.assertEqual(len(attributes), 1)
            self.assertEqual(attributes[0].event_id, second.id)
            self.assertEqual(attributes[0].timestamp.timestamp(), int(event_creation_timestamp_second.timestamp()))

            # # Test interval -6 min -> -4 min
            attributes = self.user_misp_connector.search(controller='attributes', timestamp=['6m', '4m'], pythonify=True)
            self.assertEqual(len(attributes), 1)
            self.assertEqual(attributes[0].event_id, first.id)
            self.assertEqual(attributes[0].timestamp.timestamp(), int(event_creation_timestamp_first.timestamp()))
        finally:
            # Delete event
            self.admin_misp_connector.delete_event(first.id)
            self.admin_misp_connector.delete_event(second.id)

    def test_user_perms(self):
        '''Test publish rights'''
        try:
            first = self.create_simple_event()
            first.publish()
            # Add event as user, no publish rights
            first = self.user_misp_connector.add_event(first)
            self.assertFalse(first.published)
            # Add event as publisher
            first.publish()
            first = self.pub_misp_connector.update_event(first)
            self.assertTrue(first.published)
        finally:
            # Delete event
            self.admin_misp_connector.delete_event(first.id)

    # @unittest.skip("Uncomment when adding new tests, it has a 10s sleep")
    def test_search_publish_timestamp(self):
        '''Search for a specific publication timestamp, an interval, and invalid values.'''
        # Creating event 1
        first = self.create_simple_event()
        first.publish()
        # Creating event 2
        second = self.create_simple_event()
        second.publish()
        try:
            first = self.pub_misp_connector.add_event(first)
            time.sleep(10)
            second = self.pub_misp_connector.add_event(second)
            # Test invalid query
            events = self.pub_misp_connector.search(publish_timestamp='5x', pythonify=True)
            self.assertEqual(events, [])
            events = self.pub_misp_connector.search(publish_timestamp='ad', pythonify=True)
            self.assertEqual(events, [])
            events = self.pub_misp_connector.search(publish_timestamp='aaad', pythonify=True)
            self.assertEqual(events, [])
            # Test - last 4 min
            events = self.pub_misp_connector.search(publish_timestamp='5s', pythonify=True)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].id, second.id)

            # Test 5 sec before timestamp of 2nd event
            events = self.pub_misp_connector.search(publish_timestamp=(second.publish_timestamp.timestamp()), pythonify=True)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].id, second.id)

            # Test interval -6 min -> -4 min
            events = self.pub_misp_connector.search(publish_timestamp=[first.publish_timestamp.timestamp() - 5,
                                                                       second.publish_timestamp.timestamp() - 5], pythonify=True)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].id, first.id)
        finally:
            # Delete event
            self.admin_misp_connector.delete_event(first.id)
            self.admin_misp_connector.delete_event(second.id)

    def test_simple_event(self):
        '''Search a bunch of parameters:
            * Value not existing
            * only return metadata
            * published yes/no
            * event id
            * uuid
            * creator org
            * substring search in value and eventinfo
            * quickfilter
            * date_from
            * date_to
            * deleted
            * to_ids
            * include_event_uuid
        warning list
        '''
        first = self.create_simple_event()
        first.info = 'foo bar blah'
        # First has one text attribute
        second = self.create_simple_event()
        second.info = 'foo blah'
        second.set_date('2018-09-01')
        second.add_attribute('ip-src', '8.8.8.8')
        # second has two attributes: text and ip-src
        try:
            first = self.user_misp_connector.add_event(first)
            second = self.user_misp_connector.add_event(second)
            timeframe = [first.timestamp.timestamp() - 5, first.timestamp.timestamp() + 5]
            # Search event we just created in multiple ways. Make sure it doesn't catch it when it shouldn't
            events = self.user_misp_connector.search(timestamp=timeframe, pythonify=True)
            self.assertEqual(len(events), 2)
            self.assertEqual(events[0].id, first.id)
            self.assertEqual(events[1].id, second.id)
            events = self.user_misp_connector.search(timestamp=timeframe, value='nothere', pythonify=True)
            self.assertEqual(events, [])
            events = self.user_misp_connector.search(timestamp=timeframe, value=first.attributes[0].value, pythonify=True)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].id, first.id)
            events = self.user_misp_connector.search(timestamp=[first.timestamp.timestamp() - 50,
                                                                first.timestamp.timestamp() - 10],
                                                     value=first.attributes[0].value, pythonify=True)
            self.assertEqual(events, [])

            # Test return content
            events = self.user_misp_connector.search(timestamp=timeframe, metadata=False, pythonify=True)
            self.assertEqual(len(events), 2)
            self.assertEqual(len(events[0].attributes), 1)
            self.assertEqual(len(events[1].attributes), 2)
            events = self.user_misp_connector.search(timestamp=timeframe, metadata=True, pythonify=True)
            self.assertEqual(len(events), 2)
            self.assertEqual(len(events[0].attributes), 0)
            self.assertEqual(len(events[1].attributes), 0)

            # other things
            events = self.user_misp_connector.search(timestamp=timeframe, published=True, pythonify=True)
            self.assertEqual(events, [])
            events = self.user_misp_connector.search(timestamp=timeframe, published=False, pythonify=True)
            self.assertEqual(len(events), 2)
            events = self.user_misp_connector.search(eventid=first.id, pythonify=True)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].id, first.id)
            events = self.user_misp_connector.search(uuid=first.uuid, pythonify=True)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].id, first.id)
            events = self.user_misp_connector.search(org=first.orgc_id, pythonify=True)
            self.assertEqual(len(events), 2)

            # test like search
            events = self.user_misp_connector.search(timestamp=timeframe, value='%{}%'.format(first.attributes[0].value.split('-')[2]), pythonify=True)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].id, first.id)
            events = self.user_misp_connector.search(timestamp=timeframe, eventinfo='%bar blah%', pythonify=True)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].id, first.id)

            # quickfilter
            events = self.user_misp_connector.search(timestamp=timeframe, quickfilter='%bar%', pythonify=True)
            # FIXME: should return one event
            # self.assertEqual(len(events), 1)
            # self.assertEqual(events[0].id, second.id)

            # date_from / date_to
            events = self.user_misp_connector.search(timestamp=timeframe, date_from=date.today().isoformat(), pythonify=True)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].id, first.id)
            events = self.user_misp_connector.search(timestamp=timeframe, date_from='2018-09-01', pythonify=True)
            self.assertEqual(len(events), 2)
            events = self.user_misp_connector.search(timestamp=timeframe, date_from='2018-09-01', date_to='2018-09-02', pythonify=True)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].id, second.id)

            # Category
            events = self.user_misp_connector.search(timestamp=timeframe, category='Network activity', pythonify=True)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].id, second.id)

            # toids
            events = self.user_misp_connector.search(timestamp=timeframe, to_ids='0', pythonify=True)
            self.assertEqual(len(events), 2)
            events = self.user_misp_connector.search(timestamp=timeframe, to_ids='1', pythonify=True)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].id, second.id)
            self.assertEqual(len(events[0].attributes), 1)
            events = self.user_misp_connector.search(timestamp=timeframe, to_ids='exclude', pythonify=True)
            self.assertEqual(len(events), 2)
            self.assertEqual(len(events[0].attributes), 1)
            self.assertEqual(len(events[1].attributes), 1)

            # deleted
            second.attributes[1].delete()
            self.user_misp_connector.update_event(second)
            events = self.user_misp_connector.search(eventid=second.id, pythonify=True)
            self.assertEqual(len(events[0].attributes), 1)
            events = self.user_misp_connector.search(eventid=second.id, deleted=True, pythonify=True)
            self.assertEqual(len(events[0].attributes), 2)

            # include_event_uuid
            attributes = self.user_misp_connector.search(controller='attributes', eventid=second.id, include_event_uuid=True, pythonify=True)
            self.assertEqual(attributes[0].event_uuid, second.uuid)

            # event_timestamp
            second.add_attribute('ip-src', '8.8.8.9')
            second = self.user_misp_connector.update_event(second)
            events = self.user_misp_connector.search(event_timestamp=second.timestamp.timestamp(), pythonify=True)
            self.assertEqual(len(events), 1)

            # searchall
            # FIXME: searchall doesn't seem to do anything
            # second.add_attribute('text', 'This is a test for the full text search', comment='Test stuff comment')
            # second = self.user_misp_connector.update_event(second)
            # events = self.user_misp_connector.search(value='%for the full text%', searchall=True, pythonify=True)
            # self.assertEqual(len(events), 1)
            # events = self.user_misp_connector.search(value='stuff', searchall=True, pythonify=True)
            # self.assertEqual(len(events), 1)

            # warninglist
            self.admin_misp_connector.update_warninglists()
            response = self.admin_misp_connector.toggle_warninglist(warninglist_name='%dns resolv%', force_enable=True)  # enable ipv4 DNS.
            self.assertDictEqual(response, {'saved': True, 'success': '3 warninglist(s) enabled'})
            second.add_attribute('ip-src', '1.11.71.4')
            second.add_attribute('ip-src', '9.9.9.9')
            second = self.user_misp_connector.update_event(second)

            events = self.user_misp_connector.search(eventid=second.id, pythonify=True)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].id, second.id)
            self.assertEqual(len(events[0].attributes), 4)

            events = self.user_misp_connector.search(eventid=second.id, enforce_warninglist=False, pythonify=True)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].id, second.id)
            self.assertEqual(len(events[0].attributes), 4)

            if not travis_run:
                # FIXME: This is fialing on travis for no discernable reason...
                events = self.user_misp_connector.search(eventid=second.id, enforce_warninglist=True, pythonify=True)
                self.assertEqual(len(events), 1)
                self.assertEqual(events[0].id, second.id)
                self.assertEqual(len(events[0].attributes), 2)
                response = self.admin_misp_connector.toggle_warninglist(warninglist_name='%dns resolv%')  # disable ipv4 DNS.
                self.assertDictEqual(response, {'saved': True, 'success': '3 warninglist(s) toggled'})

            time.sleep(1)  # make sure the next attribute is added one at least one second later

            # attachments
            with open('tests/testlive_comprehensive.py', 'rb') as f:
                first.add_attribute('malware-sample', value='testfile.py', data=BytesIO(f.read()))

            first = self.user_misp_connector.update_event(first)
            events = self.user_misp_connector.search(timestamp=first.timestamp.timestamp(), with_attachments=True,
                                                     pythonify=True)
            self.assertEqual(len(events), 1)
            self.assertIs(type(events[0].attributes[-1].malware_binary), BytesIO)
            events = self.user_misp_connector.search(timestamp=first.timestamp.timestamp(), with_attachments=False,
                                                     pythonify=True)
            self.assertEqual(len(events), 1)
            self.assertIs(events[0].attributes[-1].malware_binary, None)

        finally:
            # Delete event
            self.admin_misp_connector.delete_event(first.id)
            self.admin_misp_connector.delete_event(second.id)

    def test_edit_attribute(self):
        first = self.create_simple_event()
        try:
            first.attributes[0].comment = 'This is the original comment'
            first = self.user_misp_connector.add_event(first)
            first.attributes[0].comment = 'This is the modified comment'
            attribute = self.user_misp_connector.update_attribute(first.attributes[0])
            self.assertEqual(attribute.comment, 'This is the modified comment')
            attribute = self.user_misp_connector.change_comment(first.attributes[0].uuid, 'This is the modified comment, again')
            self.assertEqual(attribute['Attribute']['comment'], 'This is the modified comment, again')
        finally:
            # Delete event
            self.admin_misp_connector.delete_event(first.id)

    def test_get_csv(self):
        first = self.create_simple_event()
        second = self.create_simple_event()
        second.info = 'foo blah'
        second.set_date('2018-09-01')
        second.add_attribute('ip-src', '8.8.8.8')
        try:
            first.attributes[0].comment = 'This is the original comment'
            first = self.user_misp_connector.add_event(first)
            response = self.user_misp_connector.fast_publish(first.id, alert=False)
            self.assertEqual(response['errors'][0][1]['message'], 'You do not have permission to use this functionality.')

            # default search, all attributes with to_ids == False
            self.admin_misp_connector.fast_publish(first.id, alert=False)
            csv = self.user_misp_connector.get_csv(publish_timestamp=first.timestamp.timestamp() - 5, pythonify=True)
            # FIXME: Should not return anything (to_ids is False)
            # self.assertEqual(len(csv), 0)

            # Also export attributes with to_ids set to false
            csv = self.user_misp_connector.get_csv(publish_timestamp=first.timestamp.timestamp() - 5, ignore=True, pythonify=True)
            self.assertEqual(len(csv), 1)

            # Default search, attribute with to_ids == True
            first.attributes[0].to_ids = True
            first = self.user_misp_connector.update_event(first)
            self.admin_misp_connector.fast_publish(first.id, alert=False)
            csv = self.user_misp_connector.get_csv(publish_timestamp=first.timestamp.timestamp() - 5, pythonify=True)
            self.assertEqual(len(csv), 1)
            self.assertEqual(csv[0]['value'], first.attributes[0].value)

            # eventid
            csv = self.user_misp_connector.get_csv(eventid=first.id, pythonify=True)
            self.assertEqual(len(csv), 1)
            self.assertEqual(csv[0]['value'], first.attributes[0].value)

            # category
            csv = self.user_misp_connector.get_csv(publish_timestamp=first.timestamp.timestamp(), category='Other', pythonify=True)
            self.assertEqual(len(csv), 1)
            self.assertEqual(csv[0]['value'], first.attributes[0].value)
            csv = self.user_misp_connector.get_csv(publish_timestamp=first.timestamp.timestamp(), category='Person', pythonify=True)
            self.assertEqual(len(csv), 0)

            # type_attribute
            csv = self.user_misp_connector.get_csv(publish_timestamp=first.timestamp.timestamp(), type_attribute='text', pythonify=True)
            self.assertEqual(len(csv), 1)
            self.assertEqual(csv[0]['value'], first.attributes[0].value)
            csv = self.user_misp_connector.get_csv(publish_timestamp=first.timestamp.timestamp(), type_attribute='ip-src', pythonify=True)
            self.assertEqual(len(csv), 0)

            # context
            csv = self.user_misp_connector.get_csv(publish_timestamp=first.timestamp.timestamp(), include_context=True, pythonify=True)
            self.assertEqual(len(csv), 1)
            # print(csv[0])
            # FIXME: there is no context.

            # date_from date_to
            second = self.user_misp_connector.add_event(second)
            csv = self.user_misp_connector.get_csv(date_from=date.today().isoformat(), pythonify=True)
            self.assertEqual(len(csv), 1)
            self.assertEqual(csv[0]['value'], first.attributes[0].value)
            csv = self.user_misp_connector.get_csv(date_from='2018-09-01', date_to='2018-09-02', pythonify=True)
            self.assertEqual(len(csv), 2)

            # headerless
            csv = self.user_misp_connector.get_csv(date_from='2018-09-01', date_to='2018-09-02', headerless=True)
            # FIXME: The header is here.
            # print(csv)

        finally:
            # Delete event
            self.admin_misp_connector.delete_event(first.id)
            self.admin_misp_connector.delete_event(second.id)

    def test_upload_sample(self):
        first = self.create_simple_event()
        second = self.create_simple_event()
        third = self.create_simple_event()
        try:
            # Simple, not executable
            first = self.user_misp_connector.add_event(first)
            with open('tests/testlive_comprehensive.py', 'rb') as f:
                response = self.user_misp_connector.upload_sample(filename='testfile.py', filepath_or_bytes=f.read(),
                                                                  event_id=first.id)
            self.assertEqual(response['message'], 'Success, saved all attributes.')
            first = self.user_misp_connector.get_event(first.id)
            self.assertEqual(len(first.objects), 1)
            self.assertEqual(first.objects[0].name, 'file')
            # Simple, executable
            second = self.user_misp_connector.add_event(second)
            with open('tests/viper-test-files/test_files/whoami.exe', 'rb') as f:
                response = self.user_misp_connector.upload_sample(filename='whoami.exe', filepath_or_bytes=f.read(),
                                                                  event_id=second.id)
            self.assertEqual(response['message'], 'Success, saved all attributes.')
            second = self.user_misp_connector.get_event(second.id)
            self.assertEqual(len(second.objects), 1)
            self.assertEqual(second.objects[0].name, 'file')
            # Advanced, executable
            third = self.user_misp_connector.add_event(third)
            with open('tests/viper-test-files/test_files/whoami.exe', 'rb') as f:
                response = self.user_misp_connector.upload_sample(filename='whoami.exe', filepath_or_bytes=f.read(),
                                                                  event_id=third.id, advanced_extraction=True)
            self.assertEqual(response['message'], 'Success, saved all attributes.')
            third = self.user_misp_connector.get_event(third.id)
            self.assertEqual(len(third.objects), 7)
            self.assertEqual(third.objects[0].name, 'pe-section')
        finally:
            # Delete event
            self.admin_misp_connector.delete_event(first.id)
            self.admin_misp_connector.delete_event(second.id)
            self.admin_misp_connector.delete_event(third.id)

    def test_update_modules(self):
        # warninglist
        self.admin_misp_connector.update_warninglists()
        r = self.admin_misp_connector.update_warninglists()
        self.assertEqual(r['name'], 'All warninglists are up to date already.')
        # taxonomies
        self.admin_misp_connector.update_taxonomies()
        r = self.admin_misp_connector.update_taxonomies()
        self.assertEqual(r['name'], 'All taxonomy libraries are up to date already.')
        # object templates
        self.admin_misp_connector.update_object_templates()
        r = self.admin_misp_connector.update_object_templates()
        self.assertEqual(type(r), list)
        # notice lists
        self.admin_misp_connector.update_noticelists()
        r = self.admin_misp_connector.update_noticelists()
        self.assertEqual(r['name'], 'All noticelists are up to date already.')
        # galaxies
        self.admin_misp_connector.update_galaxies()
        r = self.admin_misp_connector.update_galaxies()
        self.assertEqual(r['name'], 'Galaxies updated.')

    @unittest.skip("Currently failing")
    def test_search_type_event_csv(self):
        try:
            first, second, third = self.environment()
            # Search as admin
            events = self.admin_misp_connector.search(return_format='csv', timestamp=first.timestamp.timestamp())
            print(events)
            attributes_types_search = self.admin_misp_connector.build_complex_query(or_parameters=['ip-src', 'ip-dst'])
            events = self.admin_misp_connector.search(return_format='csv', timestamp=first.timestamp.timestamp(),
                                                      type_attribute=attributes_types_search)
            print(events)
        finally:
            # Delete event
            self.admin_misp_connector.delete_event(first.id)
            self.admin_misp_connector.delete_event(second.id)
            self.admin_misp_connector.delete_event(third.id)


if __name__ == '__main__':
    unittest.main()
