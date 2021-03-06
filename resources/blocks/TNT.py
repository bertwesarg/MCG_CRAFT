from resources import *
import random

@register_block("TNT")
class tntblock(Block):
    blast_resistance =  0
    def block_update(self,faces):
        for face in faces:
            nachbarblockposition = self.position + face
            nachbarblock = self.world[nachbarblockposition]
            if nachbarblock["p_level"] > 0:
                self.activated(None,None)
                break

    def activated(self,character,face):
        tntrange = random.randint(3,7)
        self.world[self.position] = "AIR"
        for dx in range(-tntrange,tntrange+1):
            for dy in range(-tntrange,tntrange+1):
                for dz in range(-tntrange,tntrange+1):
                    tp = self.position+(dx,dy,dz)
                    dp = type(self.position)((dx,dy,dz))
                    self.world[tp].exploded(dp.length()/tntrange)
        
    def exploded(self,entf):
        if entf < 1:
            self.activated(None,None)
