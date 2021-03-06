# The shared.py file contains information that is relevant to client and server but does not depend on the game
# Some Funktions have been moved to __init__ but i try to get them back

import sys
if sys.version >= "3":
    raw_input = input

import zlib
import struct
import operator
import math

# list of possible events, order of bytes to transmit
ACTIONS = ["inv1","inv2","inv3","inv4","inv5","inv6","inv7","inv8",
           "inv9","inv0",
           "for" ,"back","left","right","jump","fly","inv","shift",]
DIMENSION = 3 # don't change this, it won't work

CENTER, INNER, OUTER, TOP, BOTTOM, LEFT, RIGHT = 0,1,2,4,8,16,32

#FACES = ... definition at EOF because it needs Vector class

def floatrange(a,b):
    return [i+a for i in range(0, int(math.ceil(b-a))) + [b-a]]

def hit_test(block_at_func, position, direction, max_distance=8):
    """ Line of sight search from current position.
    returns (distance, blockpos, face)
    If no block is found, return (None, None, None).

    Parameters
    ----------
    block_at_func : function used to test wether there is
        a block at a given position
    position : Vector of len 3
        The (x, y, z) position to check visibility from.
    direction : Vector of len 3
        The line of sight vector.
    max_distance : float
        How many blocks away to search for a hit.

    """
    block_pos = position.normalize()
    offset = Vector(0.5 if d > 0 else -0.5 for d in direction)
    distance = 0
    dx,dy,dz = direction
    dpx = Vector(((1 if dx > 0 else -1), 0, 0))
    dpy = Vector((0, (1 if dy > 0 else -1), 0))
    dpz = Vector((0, 0, (1 if dz > 0 else -1)))    
    l = direction.length()
    while True:
        tx,ty,tz = (block_pos+offset-position)
        kx = tx/dx if dx != 0 else float("inf")
        ky = ty/dy if dy != 0 else float("inf")
        kz = tz/dz if dz != 0 else float("inf")
        dp, k = min((dpx,kx),(dpy,ky),(dpz,kz),key=lambda t:t[1])
        distance += l*k
        if distance > max_distance:
            break
        block_pos += dp
        position += k*direction
        if block_at_func(block_pos):
            return distance, block_pos, -dp
    return None, None, None

class Ray(object):
    __slots__ = ("origin", "direction","dirfrac")
    def __init__(self, origin, direction):
        self.origin = origin
        self.direction = direction
        self.dirfrac = Vector((1.0/d if d!=0 else float("inf")) for d in direction)

class Hitbox(object):
    def __init__(self, width, height, eye_level):
        self.hitpoints = [Vector((dx,dy,dz)) for dx in floatrange(-width,width)
                                             for dy in floatrange(-eye_level,height-eye_level)
                                             for dz in floatrange(-width,width)]
        self.lb = Vector((-width, -width,       -eye_level))
        self.rt = Vector(( width,  width, height-eye_level))

    def raytest(self, position, ray):
        """ returns False if no collision else distance"""
        # https://gamedev.stackexchange.com/questions/18436/most-efficient-aabb-vs-ray-collision-algorithms
        # lb is the corner of AABB with minimal coordinates - left bottom, rt is maximal corner
        # r.org is origin of ray
        t135 = (self.lb + position - ray.origin)*ray.dirfrac
        t246 = (self.rt + position - ray.origin)*ray.dirfrac

        tmin = max(map(min,t135,t246))
        tmax = min(map(max,t135,t246))

        # if tmax < 0, ray (line) is intersecting AABB, but the whole AABB is behind us
        # if tmin > tmax, ray doesn't intersect AABB
        if (tmax < 0) or (tmin > tmax):
            return False

        return tmin
    
    def collide_blocks(self, world, position):
        blocks = set()
        for relpos in self.hitpoints:
            block_pos = (position+relpos).normalize()
            if world.get_block(block_pos).collides_with(self,position):
                blocks.add(block_pos)
        return blocks


def select(options):
    """
    Return (index, option) the user choose.
    """
    if not options:
        raise ValueError("no options given")
    print "\n".join([" ".join(map(str,option)) for option in enumerate(options)])
    print "Please enter one of the above numbers to select:",
    while True:
        i = raw_input("")
        try:
            return int(i), options[int(i)]
        except ValueError:
            print "Please enter one of the above NUMBERS to select:",
        except IndexError:
            print "Please enter ONE OF THE ABOVE numbers to select:",

class Vector(tuple):
    def _assert_same_length(self,other):
        if len(self) != len(other):
            raise ValueError("incompatible length adding vectors")
        
    def __add__(self,other):
        self._assert_same_length(other)
        return Vector(map(lambda (s,o):s+o,zip(self,other)))

    def __sub__(self,other):
        self._assert_same_length(other)
        return Vector(map(lambda (s,o):s-o,zip(self,other)))

    def __mul__(self,other):
        if isinstance(other,(float,int)):
            return Vector(map(lambda x: x*other,self))
        else:
            return Vector(map(lambda (s,o):s*o,zip(self,other)))

    def __rshift__(self,other):
        return Vector([i>>other for i in self])

    def __lshift__(self,other):
        return Vector([i<<other for i in self])

    def __mod__(self,other):
        return Vector([i%other for i in self])

    def __neg__(self):
        return Vector(-e for e in self)


    def __radd__(self,other):
        return self+other

    def __rsub__(self,other):
        return Vector(other)-self

    def __rmul__(self,other):
        return self*other


    def normalize(self):
        return Vector(map(int,map(round,self)))

    def length(self):
        return sum(map(operator.mul,self,self))**0.5
    

    def __str__(self):
        return " ".join(map(str,self))

class Chunk(object):
    """
    Not threadsave!
    #_compressed_data   -either one of these must exist when using chunk, if both exist they must be konsistent
    #_decompressed_data /
    blockformat: format string as specified by struct module
    using blockformat="H" and with 1 bit for transparency 32767 is highest possible block_id
    """
    blockformat = "H"
    byte_per_block = struct.calcsize(blockformat) #make sure to change this if you change the blockformat at runtime... better just don't change it at all

    def __init__(self,chunksize,block_codec):
        """block codec has to has at least one element (the default block)"""
        self.chunksize = chunksize
        self.block_codec = block_codec
        assert len(block_codec) >= 1

    def init_data(self):
        """fill chunk with AIR/zeros"""
        c = (1<<self.chunksize)**3*self.byte_per_block
        self.decompressed_data = bytearray(c)
        self._compressed_data = None
    
    @property
    def compressed_data(self):
        """Compressed version of the blocks in the chunk. Use this for load/store and sending to client."""
        if not self._compressed_data:
            self._compressed_data = zlib.compress(buffer(self._decompressed_data))
        return self._compressed_data
    @compressed_data.setter
    def compressed_data(self,data):
        self._compressed_data = data
        self._decompressed_data = None    

    @property
    def decompressed_data(self):
        self._load_decompressed()
        return buffer(self._decompressed_data)
    @decompressed_data.setter
    def decompressed_data(self,data):
        self._decompressed_data = bytearray(data)
        self._compressed_data = None

    def _load_decompressed(self):
        if not self._decompressed_data:
            try:
                self._decompressed_data = bytearray(zlib.decompress(self._compressed_data))
            except:
                print self._compressed_data
                raise

    def get_block_name_by_id(self,block_id):
        return self.block_codec[block_id]
    
    def get_block_id_by_name(self,block_name):
        try:
            return self.block_codec.index(block_name)
        except ValueError:
            self.block_codec.append(block_name)
            return len(self.block_codec)-1

    def __setitem__(self,key,value):
        """allow for setting slices so e.g. filling chunk by hightmap becomes easier"""
        value = self.get_block_id_by_name(value)
        self._load_decompressed()
        if isinstance(key,slice):
            s = self.byte_per_block
            vs = struct.pack(self.blockformat,value)
            start,stop,step = key.indices(len(self._decompressed_data)//s)
            l = len(xrange(start,stop,step))
            start = s*start
            stop  = s*stop
            step  = s*step
            for o,v in enumerate(vs):
                self._decompressed_data[start+o:stop+o:step] = v*l
        else:
            struct.pack_into(self.blockformat,self._decompressed_data,key*self.byte_per_block,value)
        self._compressed_data = None
        return self.get_block_name_by_id(value)

    def __getitem__(self,index):
        self._load_decompressed()
        block_id = struct.unpack_from(self.blockformat,self._decompressed_data,index*self.byte_per_block)[0]
        return self.get_block_name_by_id(block_id)

    def get_block(self,position):
        return self[self.pos_to_i(position)]

    def set_block(self,position,value):
        return self.__setitem__(self.pos_to_i(position), value)

    def pos_to_i(self, position):
        # reorder to y-first for better compression
        if not isinstance(position,Vector):
            position = Vector(position)
        position = position%(1<<self.chunksize)
        i = reduce(lambda x,y:(x<<self.chunksize)+y,position)
        return i

    def compress(self):
        """make sure data is saved ONLY in compressed form, thereby saving memory"""
        self.compressed_data #calling property makes sure _compressed_data is set
        self._decompressed_data = None


FACES = (Vector([ 0, 1, 0]), #top
         Vector([ 0,-1, 0]), #bottom
         Vector([ 0, 0, 1]), #front
         Vector([ 0, 0,-1]), #back
         Vector([-1, 0, 0]), #left
         Vector([ 1, 0, 0])) #right
