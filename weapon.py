from extract import *
from math import *

# Helper function for interpolation; this gets used a lot for distance-dependend stats
# Options for values outside range are clamp to edge and clamp to zero; the game never seems to extrapolate
def _ip(x, x0, x1, y0, y1, zero=False):
    if x0>x1: return _ip(x, x1, x0, y1, y0, zero)
    if x<x0: return 0 if zero else y0
    elif x>x1: return 0 if zero else y1
    r = (x-x0)/(x1-x0)
    return (1-r)*y0+r*y1

class Weapon: # Parse all stats of the given Weapon/Ammo/Scope combination
    def __init__(self, dataset, weapon, ammo=None, scope=None, inCover=False): # If None, use the first one that fits; MGs have different attack modes when in cover
        data = dataset.raw
        self.weapon_raw, self.ammo_raw, self.scope_raw = None, None, None
        self.attacks_raw = []
        self.enemy = False
        self.errors, self.warnings = [], []
        self.inCover = inCover and dataset.uses_cover(weapon)
        
        # Find raw weapon data
        if weapon in dataset.list_weapons( False, True, True, True):
            self.enemy = True
            self.weapon_raw = data["firearms_enemy"].Equipment.find("Firearm",{"name":weapon})
        elif weapon in dataset.list_weapons( True, False, True, False): self.weapon_raw = data["firearms_rifles"].Equipment.find("Firearm",{"name":weapon})
        elif weapon in dataset.list_weapons( True, False, False, True): self.weapon_raw = data["firearms_pistols"].Equipment.find("Firearm",{"name":weapon})
        else: self.errors += ["Weapon '%s' not found!"%weapon]
            
        # Find raw ammo data
        if ammo is None: # None given, simply take the first
            first_ammo = self.weapon_raw.AmmoTypes.Ammo["name"]
            self.ammo_raw = data["firearm_ammo"].Equipment.find("Ammo",{"name":first_ammo})
        elif ammo in dataset.list_ammo(): # Full name given; take it but do a sanity check
            self.ammo_raw = data["firearm_ammo"].Equipment.find("Ammo",{"name":ammo})
            if not self.weapon_raw.AmmoTypes.find("Ammo",{"name":ammo}):
                self.warnings += ["Weapon '%s' does not support ammo type '%s', results may be nonsense."%(weapon,ammo)]
        else: # Short name given; see if the weapon supports a matching ammo type, otherwise take the first
            for at in self.weapon_raw.AmmoTypes:
                if at.name and at["name"].startswith(ammo):
                    self.ammo_raw = data["firearm_ammo"].Equipment.find("Ammo",{"name":at["name"]})
            if not self.ammo_raw:
                first_ammo = self.weapon_raw.AmmoTypes.Ammo["name"]
                self.ammo_raw = data["firearm_ammo"].Equipment.find("Ammo",{"name":first_ammo})
                self.warnings += ["Weapon '%s' does not support ammo type '%s', using '%s' instead."%(weapon,ammo,first_ammo)]
        
        # Find raw scope data
        if scope is None and not self.enemy: # Player weapon must have a scope; if none is given, pick the first (usually IronSights)
            first_scope = self.weapon_raw.ScopeTypes.Scope["name"]
            self.scope_raw = data["firearm_scopes"].Equipment.find("Scope",{"name":first_scope})
        elif scope in dataset.list_scopes(): # Full name given; take it but do a sanity check
            self.scope_raw = data["firearm_scopes"].Equipment.find("Scope",{"name":scope})
            if self.enemy:
                self.warnings += ["Weapon '%s' does not support any scopes, results may be nonsense."%weapon]
                self.valid = False
            elif not self.weapon_raw.ScopeTypes.find("Scope",{"name":scope}):
                self.warnings += ["Weapon '%s' does not support scope type '%s', results may be nonsense."%(weapon,scope)]
                self.valid = False
        elif not self.enemy:
            first_scope = self.weapon_raw.ScopeTypes.Scope["name"]
            self.scope_raw = data["firearm_scopes"].Equipment.find("Scope",{"name":first_scope})
            self.warnings += ["Scope type '%s' does not exist, using '%s' instead."%(scope,first_scope)]
        
        # Find raw attack types
        try:
            attacks = [at for at in list(self.weapon_raw.AttackTypes) if at.name]
            self.attacks_raw = sorted([(float(at["rangeMeters"]),data["firearm_attacktypes"].FirearmAttackTypes.find("AttackType",{"name":at["name"]})) for at in attacks])
            if inCover:
                self.attacks_raw = sorted([(float(at["rangeMeters"]),data["firearm_attacktypes"].FirearmAttackTypes.find("AttackType",{"name":at["inCoverOverride"] if at.has_attr("inCoverOverride") else at["name"]})) for at in attacks])
        except:
            attacks = []
            self.errors += ["Weapon '%s' has not attack types!"%weapon]
            
    def weapon_name(self):
        return self.weapon_raw["name"]
        
    def ammo_name(self):
        try: return self.ammo_raw["name"]
        except: pass
    
    def scope_name(self):
        try: return self.scope_raw["name"]
        except: pass
    
    def info(self):
        return (self.weapon_name(), self.ammo_name(), self.scope_name(), self.inCover)
    
    def __str__(self):
        return str(self.info())
    
    def __repr__(self):
        s = "\nWeapon: "+self.weapon_name()
        if self.inCover:
            s+= " (in cover)"
        s+= "\nAmmo:   "+str(self.ammo_name())
        s+= "\nScope:  "+str(self.scope_name())
        return s
            
    def valid(self):
        return not self.errors+self.warnings 
        
    def show_errors(self):
        for err in self.errors: print(err)
        for warn in self.warnings: print(warn)
    
    def classes(self):
        return [cb["name"] for cb in self.weapon_raw.find_all("ClassBinding")]
            
    def cutoffs(self): # Distances at which stats are not smoothly interpolated (i.e. changes in attack types or scope steps)
        cutoffs={0} | {at[0] for at in self.attacks_raw}
        try:
            cutoffs |= {float(mod["minRange"]) for mod in self.scope_raw.find_all("AttackTypeModifier")}
            cutoffs |= {float(mod["maxRange"]) for mod in self.scope_raw.find_all("AttackTypeModifier")}
        except: pass
        return sorted(list(cutoffs))
    
    def can_attack(self, distance):
        return distance<=self.attacks_raw[-1][0]
    
    def attack_type(self, distance):
        for ad,at in self.attacks_raw:
            if ad>=distance: return at
        
    def attack_ranges(self, distance):
        mr = 0.0
        for ad,_ in self.attacks_raw:
            if ad>=distance: return mr, ad
            else: mr = ad
    
    def scope_mod(self, distance):
        if not self.scope_raw: return None
        for atm in self.scope_raw.Params.find_all("AttackTypeModifier"):
            if distance>=float(atm["minRange"]) and distance<=float(atm["maxRange"]):
                return atm

    def accuracy(self, distance=10):
        wps = self.weapon_raw.ModifiableParams
        acc = _ip(distance, float(wps["accuracyStartDist"]), float(wps["accuracyEndDist"]), float(wps["accuracyStart"]), float(wps["accuracyEnd"]))
        try: acc += float(self.attack_type(distance).ModifiableParams["accuracyAdd"])
        except: pass
        try: acc += float(self.scope_mod(distance).AddTo["accuracyAdd"])
        except: pass
        return acc
    
    def crit_chance(self, distance=10):
        rcc = self.ammo_raw.Params.CriticalChancePercent
        cc = _ip(distance, float(rcc["startDist"]), float(rcc["endDist"]), float(rcc["start"]), float(rcc["end"]))
        try: cc += float(self.attack_type(distance).ModifiableParams["critChanceAdd"])
        except: pass
        try: cc += float(self.scope_mod(distance).AddTo["critChanceAdd"])
        except: pass
        return cc
    
    def damage(self, distance=10):
        rd = self.ammo_raw.Params.Damage
        return _ip(distance, float(rd["startDist"]), float(rd["endDist"]), float(rd["start"]), float(rd["end"]))
    
    def followup_accuracy(self, distance=10):
        try: return float(self.attack_type(distance).ModifiableParams["followupShotAccuracyAdd"])
        except: return 0
    
    def penetration(self, distance=10):
        rp = self.ammo_raw.Params.ArmorPenetration
        return _ip(distance, float(rp["startDist"]), float(rp["endDist"]), float(rp["start"]), float(rp["end"]))
    
    def pellets(self, distance=None): # distance is irrelevant, param is just for the common interface
        try: return int(self.ammo_raw.Params["numPellets"]) # never used, but probably will be for shotgun slugs
        except: return int(self.weapon_raw.ModifiableParams["numPellets"])
    
    def burst(self, distance=10):
        try:
            atp = self.attack_type(distance).ModifiableParams
            try: return int(atp["minShots"]), int(atp["maxShots"])
            except: return 1, 1 # Found but not set - use default
        except: return 0, 0
    
    def ammo_capacity(self, distance=None, withChamber=True):
        n = int(self.weapon_raw.ModifiableParams["roundsPerMagazine"])
        if withChamber: n+=int(self.weapon_raw.ModifiableParams["closedBolt"])
        return n
    
    def aim_time(self, distance=10):
        try: minr, maxr = self.attack_ranges(distance)
        except: return inf
        atp = self.attack_type(distance).ModifiableParams
        at = _ip(distance, minr, maxr, float(atp["minAimTime"]), float(atp["maxAimTime"]))
        try:
            smod = self.scope_mod(distance)
            at += _ip(distance, float(smod["minRange"]), float(smod["maxRange"]), float(smod.AddTo["minAimTime2"]), float(smod.AddTo["maxAimTime2"]))
        except: pass
        return at
    
    def reset_time(self, distance=10):
        try: rt = float(self.attack_type(distance).ModifiableParams["resetTime"])
        except: rt = 0
        try: rt += float(self.scope_mod(distance).AddTo["resetTime"])
        except: pass
        return rt
    
    def cycle_time(self, distance=10):
        try: return 1000.0/float(self.attack_type(distance).ModifiableParams["roundsPerSecondOverride"])
        except: return 1000.0/float(self.ammo_raw.Params["roundsPerSecond"])
    
    # For the following params, distance is also irrelevant
    def guard_time(self, distance=None):
        gt = float(self.weapon_raw.ModifiableParams["guardTime"])
        try: gt += float(self.scope_raw.EquipmentModifier.AddTo["guardTime"])
        except: pass
        return gt
    
    def ready_time(self, distance=None):
        rt = float(self.weapon_raw.ModifiableParams["readyTime"])
        try: rt += float(self.scope_raw.EquipmentModifier.AddTo["readyTime"])
        except: pass
        return rt
    
    def reload_time(self, distance=None):
        rt = float(self.weapon_raw.ModifiableParams["reloadTime"])
        try: rt += float(self.scope_raw.EquipmentModifier.AddTo["reloadTime"])
        except: pass
        return rt
    
    def reload_empty_time(self, distance=None):
        rte = float(self.weapon_raw.ModifiableParams["reloadEmptyTime"])
        try: rte += float(self.scope_raw.EquipmentModifier.AddTo["reloadEmptyTime"])
        except: pass
        return rte
    
class Cached: # Parsing every single call form XML is too slow; caching is more efficient.
    def __init__(self, calculator):
        self._calculator = calculator
        self._cache = {}
    
    def empty_cache(self):
        self.cache = {}
        
    def __getattr__(self, attr):
        def method(*args):
            key = (attr,*args)
            if not key in self._cache:
                self._cache[key] = getattr(self._calculator,attr)(*args)
            return self._cache[key]
        return method
