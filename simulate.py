from weapon import *
from math import *

# Some helper functions for dealing with probabilities and events

# Useful for making sure probabilities stay between 0 and 1
def _clip(v,p0=0,p1=1): return min(max(v,p0),p1)

_eps = 1e-6 # Minimum probability to consider; one-in-a-million should be safe to ignore

# The basic structure that represents possible outcomes as a map of {(time,damage):probability}
# It's basically a probability tree that gets collapsed immediately
class Event:
    def __init__(self, t=None, d=0, p=1):
        if isinstance(t,dict): self.outcomes=t
        elif t is not None: self.outcomes = {(int(t),int(d)):_clip(float(p))}
        else: self.outcomes={}
    
    def add_outcome(self, time, damage, p):
        key = (int(time),int(damage))
        if key in self.outcomes: self.outcomes[key]+=p
        else: self.outcomes[key]=p
    
    def __add__(self, other):
        out = Event(self.outcomes.copy())
        for k,p in other.outcomes.items():
            if k in out.outcomes:
                out.outcomes[k]+=p
            else: out.outcomes[k]=p
        return out
        
    def __rmul__(self, p): # Probabilites can be multiplied from the left, and float has no overload to multiply with Event 
        prod = Event()
        prod.outcomes = {k:v*p for k,v in self.outcomes.items()}
        return prod
    
    def __mul__(self, other):
        if not isinstance(other, Event):
            return other*self # Make sure it's not a float; in that case, use __rmul__
        prod = Event()
        for (st,sd),sp in self.outcomes.items():
            for (ot,od),op in other.outcomes.items():
                prod.add_outcome(st+ot,sd+od,sp*op)
        return prod
    
    def __repr__(self):
        if not self.outcomes: # The expected value would cause a division by zero here
            return "\n%6d ms: %6d damage with p = %1.3f"%(0,0,0)
        out="\n"
        for (t,d),p in self.outcomes.items():
            out+="%6d ms: %6d damage with p = %1.3f\n"%(t,d,p)
        out+="---------------------------------------\n"
        out+="%6d ms: %9.2f dmg with p = %1.3f"%(*self.expected(),self.total())
        return out
    
    def __str__(self):
        return str(self.outcomes)
    
    def __bool__(self):
        return bool(self.outcomes)
    
    def total(self):
        return sum(self.outcomes.values())
    
    def normalize(self):
        n = 1/self.total()
        for key in self.outcomes:
            self.outcomes[key]*=n
    
    def normalized(self):
        n = 1/self.total()
        return n*self
    
    def expected(self):
        if not self.outcomes: return inf, 0
        tt, td, tp = 0, 0, 0
        for (t,d),p in self.normalized().outcomes.items():
            tt+=t*p
            td+=d*p
            tp+=p
        return tt,td
    
    def capped(self, max_hp=100):
        ev2 = Event()
        for (t,d),p in self.outcomes.items():
            ev2.add_outcome(t,min(d,max_hp),p)
        return ev2
        
    def cap(self, max_hp=100):
        self.outcomes = self.capped(max_hp).outcomes
    
    def split_by_damage(self, damage=100):
        alive, dead = Event(), Event()
        for (t,d),p in self.outcomes.items():
            if d<damage: alive.add_outcome(t,d,p)
            else: dead.add_outcome(t,d,p)
        return alive, dead

    def split_by_time(self, timeout=10000):
        before, after = Event(), Event()
        for (t,d),p in self.outcomes.items():
            if t<timeout: before.add_outcome(t,d,p)
            else: after.add_outcome(t,d,p)
        return before, after
    
    def dps(self):
        t,d = self.expected()
        if t<=0: return 0
        else: return 1000*d/t
    
    def kill_chance(self, hp=100):
        return self.split_by_damage(hp)[1].total()
    
    def kill_time(self, pmin=0.5, hp=100):
        tp, tmax = 0, 0
        a,d = self.split_by_damage(hp)
        for (t,_),p in d.outcomes.items():
            tp += p
            if tp>=pmin: return t
        for (t,dmg),p in sorted(a.outcomes.items(),key=lambda x: x[0][0]/x[0][1] if x[0][1]>0 else inf):
            tp += p
            if dmg>0:
                tmax=max(tmax, t/dmg*hp)
                if tp>pmin: return t/dmg*hp
        if tp>0: return tmax/tp*pmin
        else: return inf
    
# Armor is (piercing, coverage%); Assumption: Crits ignore armor
def one_pellet(gun, distance=10, followup=0, max_hp=100, armor=(0,0), cover=False):
    event = Event()
    ca = _clip((gun.accuracy(distance)+followup*gun.followup_accuracy(distance))*0.01)
    if cover: ca*=0.5 # Not sure if this is true, but feels about right
    cc = _clip(gun.crit_chance(distance)*.01)
    if ca>0:
        if cc>0: event.add_outcome(0,max_hp,ca*cc)
        if cc<1:
            if gun.penetration(distance)<armor[0]:
                if armor[1]>0: event.add_outcome(0,1,ca*(1-cc)*armor[1]*0.01)
                if armor[1]<100: event.add_outcome(0,gun.damage(distance),ca*(1-cc)*(1-armor[1]*0.01))
            else: event.add_outcome(0,gun.damage(distance),ca*(1-cc))
    if ca<1: event.add_outcome(0,0,1-ca)
    return event

def one_shot(gun, distance=10, followup=0, max_hp=100, armor=(0,0), cover=False):
    p1 = one_pellet(gun, distance, followup, max_hp, armor, cover)
    np = gun.pellets()
    if np<=1: return p1*Event(gun.cycle_time(distance))
    else:
        shot = Event(0)
        for p in range(np):
            shot=shot*p1
    return shot.capped(max_hp)*Event(gun.cycle_time(distance))

# expects a list [(shots,event)], returns a single event
def collapse(events):
    collapsed = Event()
    for _,ev in events: collapsed = collapsed + ev
    return collapsed

def one_burst(gun, distance=10, followup=0, max_hp=100, armor=(0,0), cover=False, ammo_used=0, collapsed=True):
    # The doc isn't 100% clear on this, but my assumption is that the timing for, e.g. a 3-Round-Burst works like this:
    # Wait for aimTime, fire one shot, wait for 1/rps, fire one shot, wait for 1/rps, fire one shot, wait for 1/rps (???), wait for resetTime
    # I also assume followupAccuracy carries over between shot sequences, since the parameter is non-zero for some one-shot "sequences"
    # if collapsed==False, the function returns a list of (shots,event) because the number of shots fired must be tracked
    shots_left = gun.ammo_capacity()-followup-ammo_used
    bmin, bmax = gun.burst(distance)
    bmin = min(bmin, shots_left)
    bmax = min(bmax, shots_left)
    out = []
    if shots_left<1: pass # Gun empty, nothing happens
    elif bmax==0: pass # Target out of range, nothing happens
    elif bmax<0: # =-1: will shoot until enemy is dead or gun is empty (i.e. may end early)
        sequence = Event(gun.aim_time(distance)+gun.reset_time(distance))
        for i in range(shots_left):
            sequence = sequence*one_shot(gun,distance,followup+i,max_hp,armor,cover)
            if i>=bmin-1:
                alive, dead = sequence.split_by_damage(max_hp)
                if alive.total()<_eps: break
                if dead.total()>_eps: out+=[(i+1,dead.capped(max_hp))]
                sequence = alive
        out+=[(i+1,sequence.capped(max_hp))]
    else: # >0: the full number of rounds will always be fired
        p = 1/(1+bmax-bmin)
        for n in range(bmin, bmax+1):
            sequence = Event(gun.aim_time(distance)+gun.reset_time(distance))
            for i in range(n):
                sequence=sequence*one_shot(gun,distance,followup+i,max_hp,armor,cover)
            out+=[(n,p*sequence.capped(max_hp))]
    if collapsed: return collapse(out)
    else: return out

def one_mag(gun, distance=10, ammo_used=0, max_hp=100, armor=(0,0), cover=False, timeout=10000, collapsed=True):
    # Will keep firing until either the mag is empty (and add reload time), the enemy is dead (and not add reload time), or timeout is reached (otherwise, MGs can take very, very long to resolve)
    current_events = [(0,Event(0))]
    resolved_events = []
    while current_events:
        new_events=[]
        for s,ev in current_events:
            if s>=gun.ammo_capacity()-ammo_used:
                resolved_events+=[(s,ev*Event(gun.reload_empty_time()))]
                continue
            a,d = ev.split_by_damage(max_hp)
            if d.total()>_eps: resolved_events+=[(s,d)]
            if a.total()>_eps:
                if gun.accuracy(distance)+s*gun.followup_accuracy(distance)>0:
                    burst = one_burst(gun, distance, s, max_hp, armor, cover, ammo_used, False)
                    for s2, e2 in burst:
                        new_events+=[(s+s2,(a*e2).capped(max_hp))]
                    if not burst: # Failed to fire
                        resolved_events+=[(s,a)]
                else: resolved_events+=[(s,a)]
        if timeout:
            current_events = []
            for s,e in new_events:
                b,a = e.split_by_time(timeout)
                if b.total()>_eps: current_events+=[(s,b)]
                if a.total()>_eps: resolved_events+=[(s,a)]
        else: current_events = new_events
    if collapsed: return collapse(resolved_events)
    else: return resolved_events
