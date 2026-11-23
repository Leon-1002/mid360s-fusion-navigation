import unittest
from joint_test import assess_frames

class JointTests(unittest.TestCase):
    def frames(self):
        return [dict(blockId=100+i,status=0,width=3072,height=2048,size=3072*2048,
                     pixelFormat=0x01080009,timeStamp=1000000+i*200000,
                     host_monotonic=100+i*.2) for i in range(300)]
    def test_exact_batch(self):
        self.assertTrue(assess_frames(self.frames(),300)['pass'])
    def test_missing_extra_or_mismatched_pulses(self):
        frames=self.frames()
        self.assertFalse(assess_frames(frames[:-1],300)['pass'])
        self.assertFalse(assess_frames(frames+[frames[-1]],300)['pass'])
        self.assertFalse(assess_frames(frames,299)['pass'])
    def test_corrupt_frame_or_wrong_format(self):
        for key,value in [('status',1),('width',640),('size',10),('pixelFormat',0)]:
            frames=self.frames(); frames[150][key]=value
            self.assertFalse(assess_frames(frames,300)['pass'],key)
    def test_id_gap_and_clock_reversal(self):
        for key,value in [('blockId',9999),('timeStamp',0)]:
            frames=self.frames(); frames[150][key]=value
            self.assertFalse(assess_frames(frames,300)['pass'],key)
    def test_wrong_cadence(self):
        frames=self.frames()
        for i,frame in enumerate(frames): frame['host_monotonic']=100+i*.3
        self.assertFalse(assess_frames(frames,300)['pass'])

if __name__=='__main__': unittest.main(verbosity=2)
