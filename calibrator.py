"""
Has the logic to perform the various calibration routines by reading data
via a Snapshot class and modifying ADC parameters via and IAdc class
"""

import logging
import time

class Calibrator:
    def __init__(self, iadc, adc_data_wrapper, interleaved=False, logger=logging.getLogger(__name__)):
        """ Calibrator is contains logic for calibration routines
        
        iadc -- instance of IAdc which is used for modifying parameters
        snapshot -- instance of Snapshot which has been initialised to the
            same ADC ZDOK as iadc has.
        interleaved -- if True, read data interleaved from RF input I.
            If False, read I and Q seperately.
        """
        self.logger = logger
        self.iadc = iadc
        self.zdok_n = iadc.zdok_n
        self.adw = adc_data_wrapper
        self.interleaved = interleaved

    def run_offset_cal(self):
        """ Performs offset calibration by attempting to ensure that both 
        I and Q have 0 mean.
        """
        if self.interleaved == True:
            self.snapshot.set_mode('inter')
            # iadc.set_mode('inter')
            self.run_offset_cal_for_single_channel('inter')
        else:
            for channel in ('I', 'Q'):
                # iadc.set_mode...
                self.run_offset_cal_for_single_channel(channel)

    def run_offset_cal_for_single_channel(self, channel):
        """ The channel should have already been defined on the ADC and in the 
        instance of Snapshot
        This reads from the snapshot and attempts to get the mean to 0
        
        channel -- what should be read from the snapshot block
        """
        self.adw.resample()
        new_mean = self.adw.get_offset(channel) # should have a magnitute somewhere between 0 and 4
        self.logger.info("Before clibration, offset = {o} for channel {c}".format(c = channel, o = new_mean))
        if(new_mean > 0):  # we want to decrease the offset
            while(new_mean > 0):
                assert(self.iadc.offset_dec(channel) == True) # should never hit bottom
                last_mean = new_mean
                time.sleep(0.1)  # some time for the change to 'apply'
                self.adw.resample()
                new_mean = self.adw.get_offset(channel)
                assert(new_mean < last_mean)
            # fix if we have gone too far
            if(abs(new_mean) > abs(last_mean)):
               self.iadc.offset_inc(channel)
        elif(new_mean < 0):  # we want to increase the offset
            while(new_mean < 0):
                assert(self.iadc.offset_inc(channel) == True)
                last_mean = new_mean
                time.sleep(0.1)
                self.adw.resample()
                new_mean = self.adw.get_offset(channel)
            if(abs(new_mean) > abs(last_mean)):
               self.iadc.offset_dec(channel)
        time.sleep(0.1)
        self.adw.resample()
        new_mean = self.adw.get_offset(channel)
        self.logger.info("After clibration, offset = {o} for channel {c}".format(c = channel, o = new_mean))

    def run_phase_difference_cal(self, interleaved=False):
        """ Attempts to get the phase difference between the channels
        down to 0
        """
        self.adw.resample()
        new_phase = self.adw.get_phase_difference()
        self.logger.info("Before clibration phase difference = {p}".format(p = new_phase))
        if(new_phase > 0):  # I ahead of Q. 
            while(new_phase > 0):
                assert(self.iadc.fisda_inc() == True) # decrease the Q delay (advance Q)
                last_phase = new_phase
                time.sleep(0.1)  # some time for the change to 'apply'
                self.adw.resample()
                new_phase = self.adw.get_phase_difference()
                assert(new_phase < last_phase)
            # fix if we have gone too far
            if(abs(new_phase) > abs(last_phase)):
               self.iadc.fisda_dec()  # advanced Q too much. Inc the Q delay.
        elif(new_phase < 0):  # we want to increase the offset
            while(new_phase < 0):
                assert(self.iadc.fisda_dec() == True)  # delay Q. 
                last_phase = new_phase
                time.sleep(0.1)
                self.adw.resample()
                new_phase = self.adw.get_phase_difference()
            if(abs(new_phase) > abs(last_phase)):
               self.iadc.fisda_inc()
        time.sleep(0.1)
        self.adw.resample()
        new_phase = self.adw.get_phase_difference()
        self.logger.info("After calibration phase difference: {ph}".format(ph = new_phase))

    def run_analogue_gain_cal(self, interleaved=False):
        """Attempts to get the sum of the squared output values to be equal for each channel.
        """
        raise Exception("Not really implemented properly yet...")
        self.snapshot.set_mode('IQ')
        sums_squared = self.snapshot.get_sum_squared()
        channel_I_sum = sums_squared['I']
        channel_Q_sum = sums_squared['Q']
        self.logger.info("Before calibration, channel I sum squared: {i}, channel Q sum squared: {q}, difference: {d}".format(
            i = channel_I_sum, q = channel_Q_sum, d = abs(channel_I_sum - channel_Q_sum)))
        # increment the smaller and decrement the larger until approximately equal.
        while(channel_I_sum > channel_Q_sum):
            self.iadc.analogue_gain_dec('I')
            channel_I_sum = self.snapshot.get_sum_squared()['I']
            if(channel_I_sum > channel_Q_sum):
                self.iadc.analogue_gain_inc('Q')
                channel_Q_sum = self.snapshot.get_sum_squared()['Q']
        while(channel_I_sum < channel_Q_sum):
            self.iadc.analogue_gain_inc('I')
            channel_I_sum = self.snapshot.get_sum_squared()['I']
            if(channel_I_sum < channel_Q_sum):
                self.iadc.analogue_gain_dec('Q')
                channel_Q_sum = self.snapshot.get_sum_squared()['Q']
        # channel_I must now be greater than channel_Q
        before_difference = channel_I_sum - channel_Q_sum
        self.iadc.analogue_gain_inc('Q')
        channel_Q_sum = self.snapshot.get_sum_squared()['Q']
        after_difference = abs(channel_Q_sum - channel_I_sum)  # abs just in case it's marginally greater (approx equal)
        if(before_difference < after_difference):  # if going lower was a bad idea...
            self.iadc.analogue_gain_dec('Q')  # ...go back up
        sums_squared = self.snapshot.get_sum_squared()
        channel_I_sum = sums_squared['I']
        channel_Q_sum = sums_squared['Q']
        self.logger.info("After calibration, channel I sum squared: {i}, channel Q sum squared: {q}, difference: {d}".format(
            i = channel_I_sum, q = channel_Q_sum, d = abs(channel_I_sum - channel_Q_sum)))
