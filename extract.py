from bs4 import BeautifulSoup
from glob import glob
from os.path import basename, splitext

class Data:
    def __init__(self, datapath="data"):
        xmlfiles = glob(datapath+"/equipment/*.xml")
        self.raw = {splitext(basename(xf))[0]:BeautifulSoup(open(xf,'r'),"xml") for xf in xmlfiles}

    def item_names(self, obj="Firearm", slot=None, files=None): # None means "any"
        names = []
        if not files:
            files = self.raw.keys()
        for fn in files:
            try:
                if slot: names+=[item["name"] for item in self.raw[fn].Equipment.find_all(obj,{"inventoryBinding":slot})]
                else: names+=[item["name"] for item in self.raw[fn].Equipment.find_all(obj)]
            except: pass # File many not contain any equipment
        return names

    def list_weapons(self, player=True, enemy=False, primary=True, secondary=False):
        ws = []
        if player and primary: ws+=self.item_names(obj="Firearm", slot="PrimaryWeapon", files=["firearms_rifles"])
        if player and secondary: ws+=self.item_names(obj="Firearm", slot="SecondaryWeapon", files=["firearms_pistols"])
        if enemy and primary: ws+=self.item_names(obj="Firearm", slot="PrimaryWeapon", files=["firearms_enemy"])
        if enemy and secondary: ws+=self.item_names(obj="Firearm", slot="SecondaryWeapon", files=["firearms_enemy"])
        return ws

    def list_scopes(self, primary=True, secondary=False): # Enemies don't use scopes at all, and pistols only have iron sights
        s = []
        if primary: s+=self.item_names(obj="Scope", slot="PrimaryWeaponScope", files=["firearm_scopes"])
        if secondary: s+=self.item_names(obj="Scope", slot="SecondaryWeaponScope", files=["firearm_scopes"])
        return s

    def list_ammo(self, summary=False):
        if summary: return list({an.split('_')[0] for an in self.item_names(obj="Ammo",files=["firearm_ammo"])})
        else: return self.item_names(obj="Ammo",files=["firearm_ammo"])

    def find_weapon_entry(self, weapon):
        if weapon in self.list_weapons(False, True, True, True): return self.raw["firearms_enemy"].Equipment.find("Firearm",{"name":weapon})
        elif weapon in self.list_weapons(True, False, True, False): return self.raw["firearms_rifles"].Equipment.find("Firearm",{"name":weapon})
        elif weapon in self.list_weapons(True, False, False, True): return self.raw["firearms_pistols"].Equipment.find("Firearm",{"name":weapon})

    def list_scopes_for(self, weapon):
        return [s["name"] for s in self.find_weapon_entry(weapon).find_all("Scope")]

    def list_ammo_for(self, weapon):
        return [a["name"] for a in self.find_weapon_entry(weapon).find_all("Ammo")]
    
    def list_classes_for(self, weapon):
        return [c["name"] for c in self.find_weapon_entry(weapon).find_all("ClassBinding")]

    def uses_cover(self, weapon):
        return any([at.has_attr("inCoverOverride") for at in self.find_weapon_entry(weapon).find_all("AttackType")])
    
if __name__=="__main__":
    from sys import argv
    try: data = Data(argv[1])
    except: data = Data()
    print("\nFound Primary Weapons (Player):")
    for w in data.list_weapons(True, False, True, False): print(w)
    print("\nFound Secondary Weapons (Player):")
    for w in data.list_weapons(True, False, False, True): print(w)
    print("\nFound Primary Weapons (Enemy):")
    for w in data.list_weapons(False, True, True, False): print(w)
    print("\nFound Secondary Weapons (Enemy):")
    for w in data.list_weapons(False, True, False, True): print(w)
    print("\nFound Primary Scopes:")
    for s in data.list_scopes(True, False): print(s)
    print("\nFound Secondary Scopes:")
    for s in data.list_scopes(False, True): print(s)
    print("\nFound Ammo Types:")
    for a in data.list_ammo(True): print(a)
    print("\nFound Ammo/Weapon Combinations:")
    for a in data.list_ammo(False): print(a)
    print()
