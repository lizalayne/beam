#
# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""Unit tests for the Create and _CreateSource classes."""
import unittest

from apache_beam.io import source_test_utils

from apache_beam import Create, assert_that, equal_to
from apache_beam.coders import FastPrimitivesCoder
from apache_beam.test_pipeline import TestPipeline


class CreateTest(unittest.TestCase):
  def setUp(self):
    self.coder = FastPrimitivesCoder()

  def test_create_transform(self):
    with TestPipeline() as p:
      assert_that(p | Create(range(10)), equal_to(range(10)))

  def test_create_source_read(self):
    self.check_read([], self.coder)
    self.check_read([1], self.coder)
    # multiple values.
    self.check_read(range(10), self.coder)

  def check_read(self, values, coder):
    source = Create._create_source_from_iterable(values, coder)
    read_values = source_test_utils.readFromSource(source)
    self.assertEqual(sorted(values), sorted(read_values))

  def test_create_source_read_with_initial_splits(self):
    self.check_read_with_initial_splits([], self.coder, num_splits=2)
    self.check_read_with_initial_splits([1], self.coder, num_splits=2)
    values = range(8)
    # multiple values with a single split.
    self.check_read_with_initial_splits(values, self.coder, num_splits=1)
    # multiple values with a single split with a large desired bundle size
    self.check_read_with_initial_splits(values, self.coder, num_splits=0.5)
    # multiple values with many splits.
    self.check_read_with_initial_splits(values, self.coder, num_splits=3)
    # multiple values with uneven sized splits.
    self.check_read_with_initial_splits(values, self.coder, num_splits=4)
    # multiple values with num splits equal to num values.
    self.check_read_with_initial_splits(values, self.coder,
                                        num_splits=len(values))
    # multiple values with num splits greater than to num values.
    self.check_read_with_initial_splits(values, self.coder, num_splits=30)

  def check_read_with_initial_splits(self, values, coder, num_splits):
    """A test that splits the given source into `num_splits` and verifies that
    the data read from original source is equal to the union of the data read
    from the split sources.
    """
    source = Create._create_source_from_iterable(values, coder)
    desired_bundle_size = source._total_size / num_splits
    splits = source.split(desired_bundle_size)
    splits_info = [
        (split.source, split.start_position, split.stop_position)
        for split in splits]
    source_test_utils.assertSourcesEqualReferenceSource((source, None, None),
                                                        splits_info)

  def test_create_source_read_reentrant(self):
    source = Create._create_source_from_iterable(range(9), self.coder)
    source_test_utils.assertReentrantReadsSucceed((source, None, None))

  def test_create_source_read_reentrant_with_initial_splits(self):
    source = Create._create_source_from_iterable(range(24), self.coder)
    for split in source.split(desired_bundle_size=5):
      source_test_utils.assertReentrantReadsSucceed((split.source,
                                                     split.start_position,
                                                     split.stop_position))

  def test_create_source_dynamic_splitting(self):
    # 2 values
    source = Create._create_source_from_iterable(range(2), self.coder)
    source_test_utils.assertSplitAtFractionExhaustive(source)
    # Multiple values.
    source = Create._create_source_from_iterable(range(11), self.coder)
    source_test_utils.assertSplitAtFractionExhaustive(
        source, perform_multi_threaded_test=True)

  def test_create_source_progress(self):
    num_values = 10
    source = Create._create_source_from_iterable(range(num_values), self.coder)
    splits = [split for split in source.split(desired_bundle_size=100)]
    assert len(splits) == 1
    fraction_consumed_report = []
    split_points_report = []
    range_tracker = splits[0].source.get_range_tracker(
        splits[0].start_position, splits[0].stop_position)
    for _ in splits[0].source.read(range_tracker):
      fraction_consumed_report.append(range_tracker.fraction_consumed())
      split_points_report.append(range_tracker.split_points())

    self.assertEqual(
        [float(i) / num_values for i in range(num_values)],
        fraction_consumed_report)

    expected_split_points_report = [
        ((i - 1), num_values - (i - 1))
        for i in range(1, num_values + 1)]

    self.assertEqual(
        expected_split_points_report, split_points_report)
