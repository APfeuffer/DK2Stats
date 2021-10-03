from simulate import *

all_sides = ["Player", "Enemy"]
all_slots = ["Primary", "Secondary"]
player_classes = ["Assault", "Support", "Marksman", "Medic", "Grenadier"]

def match_weapons(data, sides=None, slots=None, classes=None, weapons=None, ammo=None, scopes=None, in_cover=None): # None matches any
    weaponlist = []
    if sides is None: sides = all_sides
    if slots is None: slots = all_slots
    for wname in data.list_weapons("Player" in sides, "Enemy" in sides, "Primary" in slots, "Secondary" in slots):
        if weapons is not None and not wname in weapons: continue
        if classes is not None:
            matched = False
            for cls in data.list_classes_for(wname):
                if cls in classes:
                    matched = True
            if not matched: continue
        for aname in data.list_ammo_for(wname):
            if ammo is not None and not any([aname.startswith(a)] for a in ammo): continue
            for sname in data.list_scopes_for(wname):
                if scopes is not None and not sname in scopes: continue
                if in_cover is None and data.uses_cover(wname):
                    weaponlist.append(Weapon(data,wname,aname,sname,False))
                    weaponlist.append(Weapon(data,wname,aname,sname,True))
                else: weaponlist.append(Weapon(data,wname,aname,sname,bool(in_cover)))
            if (not data.list_scopes_for(wname)) and scopes is None:
                if in_cover is None and data.uses_cover(wname):
                    weaponlist.append(Weapon(data,wname,aname,None,False))
                    weaponlist.append(Weapon(data,wname,aname,None,True))
                else: weaponlist.append(Weapon(data,wname,aname,None,bool(in_cover)))
    return [weapon for weapon in weaponlist if weapon.valid]

def all_cutoffs(weapons):
    cuts = set()
    for w in weapons:
        cuts|=set(w.cutoffs())
    return sorted(list(cuts))

def x_axis(points, split_at=[], split_size=1e-3, max_steps_per_meter=10):
    axis = []
    scaled_steps = set([int(p*max_steps_per_meter) for p in points])
    scaled_splits = set([int(s*max_steps_per_meter) for s in split_at])
    for p in scaled_steps|scaled_splits:
        if p in scaled_splits:
            pl, pr = p/max_steps_per_meter-split_size, p/max_steps_per_meter+split_size
            if pl>=min(points) and pl<=max(points): axis+=[pl]
            if pr>=min(points) and pr<=max(points): axis+=[pr]
        else:
            axis+=[p/max_steps_per_meter]
    return sorted(axis)

def make_table(weapons, distances, y_function, colsep=';', rowsep='\n'): # y_function is any function that takes a weapon and a distance and returns a number
    table = colsep.join(["Weapon","Ammo","Scope","inCover"]+[str(x) for x in distances])+rowsep
    for weapon in weapons:
        print("Calculating:",weapon)
        cells = [*weapon.info()]+[y_function(Cached(weapon),x) for x in distances]
        table += colsep.join([str(c) for c in cells])+rowsep
    return table

if __name__=="__main__":
    from sys import argv
    from os import makedirs
    try: data = Data(argv[1])
    except: data = Data()
    weapons = match_weapons(data)
    #weapons = match_weapons(data, sides=["Enemy"])
    #weapons = match_weapons(data, classes=["Assault"], slots=["Primary"])
    #weapons = match_weapons(data, weapons=["M4 Carbine"])
    #weapons = match_weapons(data, weapons=["SniperRifle"])
    cuts = all_cutoffs(weapons)
    xs = x_axis(range(0,101,5),cuts)
    outdir = "output/"
    makedirs(outdir, exist_ok=True)
    tasks = [
        ("base_damage.csv", lambda w,x: w.damage(x)),
        ("accuracy.csv", lambda w,x: w.accuracy(x)),
        ("crit_chance.csv", lambda w,x: w.crit_chance(x)),
        ("aim_time.csv", lambda w,x: w.aim_time(x)),
        ("rate_of_fire.csv", lambda w,x: 1000.0/w.cycle_time(x)),
        ("effective_damage.csv", lambda w,x: one_shot(w,x).expected()[1]),
        ("burst_kill_chance.csv", lambda w,x: one_burst(w,x).kill_chance()),
        ("burst_time.csv", lambda w,x: one_burst(w,x).expected()[0]),
        ("burst_damage.csv", lambda w,x: one_burst(w,x).expected()[1]),
        ("damage_per_second.csv", lambda w,x: one_burst(w,x).dps()),
        ("kill_time_50_percent.csv", lambda w,x: one_burst(w,x).kill_time(0.5)),
        ("kill_time_95_percent.csv", lambda w,x: one_burst(w,x).kill_time(0.95)),
        ("damage_per_second_with_reload.csv", lambda w,x: one_mag(w,x).dps()),
        ("kill_time_50_percent_with_reload.csv", lambda w,x: one_mag(w,x).kill_time(0.5)),
        ("kill_time_95_percent_with_reload.csv", lambda w,x: one_mag(w,x).kill_time(0.95))
        ]
    for filename, yfunc in tasks:
        print("Next table:",outdir+filename)
        with open(outdir+filename,'w') as f:
            f.write(make_table(weapons, xs, yfunc))
