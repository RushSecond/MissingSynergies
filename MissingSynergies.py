from RareMonsters import *
from Upgrades import *
from Spells import *
from Level import *
from CommonContent import *
from Monsters import *
from Variants import *
import random, math, os, sys

from mods.BugsAndScams.Bugfixes import RemoveBuffOnPreAdvance
import mods.BugsAndScams.Bugfixes

if "mods.BugsAndScams.NoMoreScams" in sys.modules:
    is_immune = sys.modules["mods.BugsAndScams.NoMoreScams"].is_immune
else:
    is_immune = lambda target, source, damage_type: target.resists[damage_type] >= 100

def send_bolts(effect_path, effect_target, origin, targets):

    def bolt(target):
        for point in Bolt(origin.level, origin, target):
            effect_path(point)
            yield True
        effect_target(target)
        yield False

    bolts = [bolt(target) for target in targets]
    while bolts:
        bolts = [bolt for bolt in bolts if next(bolt)]
        yield

def drain_max_hp_kill(unit, hp):
    if unit.max_hp > hp:
        drain_max_hp(unit, hp)
    else:
        unit.max_hp = 1
        unit.cur_hp = 0
        unit.kill()

class BitterCurse(Buff):
    def __init__(self, spell):
        self.spell = spell
        Buff.__init__(self)

    def on_init(self):
        self.buff_type = BUFF_TYPE_CURSE
        self.name = "Bitter Curse"
        self.color = Tags.Holy.color
        self.owner_triggers[EventOnPreDamaged] = self.on_pre_damaged
        self.asset = ["MissingSynergies", "Statuses", "wormwood"]
    
    def on_pre_damaged(self, evt):
        if evt.damage_type != Tags.Poison:
            return
        evt.unit.deal_damage(evt.damage, Tags.Holy, self.spell)
        poison = evt.unit.get_buff(Poison)
        if poison:
            poison.turns_left += evt.damage
        else:
            evt.unit.apply_buff(Poison(), evt.damage)
    
    # For my No More Scams mod
    def can_redeal(self, target, source, damage_type):
        return damage_type == Tags.Poison and target.resists[Tags.Holy] < 100

class WormwoodSpell(Spell):

    def on_init(self):
        self.name = "Wormwood"
        self.asset = ["MissingSynergies", "Icons", "wormwood"]

        self.damage = 33
        self.radius = 6
        self.range = RANGE_GLOBAL
        self.requires_los = False
        self.duration = 6
        self.can_target_self = True

        self.max_charges = 1

        self.tags = [Tags.Holy, Tags.Nature, Tags.Sorcery, Tags.Enchantment]
        self.level = 7

        self.upgrades["radius"] = (3, 2)
        self.upgrades["duration"] = (3, 3)
        self.upgrades["damage"] = (33, 3)
        self.upgrades["max_charges"] = (1, 2)

    def get_description(self):
        return ("Call down a bitter star. All enemies in a [{radius}_tile:radius] radius are afflicted with Bitter Curse for [{duration}_turns:duration], then dealt [{damage}_poison:poison] damage.\n"
                "[Poison] damage dealt to a unit with Bitter Curse is redealt as [holy] damage, and inflicts [poison] for that many turns, before counting resistances; this stacks with any pre-existing [poison] they have.").format(**self.fmt_dict())
    
    def cast_instant(self, x, y):
        duration = self.get_stat("duration")
        damage = self.get_stat("damage")
        for p in self.caster.level.get_points_in_ball(x, y, self.get_stat("radius")):
            self.caster.level.show_effect(p.x, p.y, Tags.Holy)
            self.caster.level.show_effect(p.x, p.y, Tags.Poison)
            unit = self.caster.level.get_unit_at(p.x, p.y)
            if unit and are_hostile(unit, self.caster):
                unit.apply_buff(BitterCurse(self), duration)
                unit.deal_damage(damage, Tags.Poison, self)

class IrradiateBuff(Buff):
    def __init__(self, spell):
        self.spell = spell
        Buff.__init__(self)

    def on_init(self):
        self.buff_type = BUFF_TYPE_CURSE
        self.name = "Irradiated"
        self.color = Tags.Arcane.color
        self.asset = ["MissingSynergies", "Statuses", "irradiate"]
        if self.spell.get_stat("fallout"):
            self.owner_triggers[EventOnDeath] = self.on_death

    def on_advance(self):

        radius = 0
        poison = self.owner.get_buff(Poison)
        if poison:
            radius = math.ceil(poison.turns_left/10)

        effects_left = 7

        for unit in self.owner.level.get_units_in_ball(Point(self.owner.x, self.owner.y), radius):

            if are_hostile(self.owner, unit):
                continue

            damage_type = random.choice([Tags.Arcane, Tags.Poison])
            unit.deal_damage(2, damage_type, self.spell)
            effects_left -= 1

        # Show some graphical indication of this aura if it didnt hit much
        points = self.owner.level.get_points_in_ball(self.owner.x, self.owner.y, radius)
        points = [p for p in points if not self.owner.level.get_unit_at(p.x, p.y)]
        random.shuffle(points)
        for i in range(effects_left):
            if not points:
                break
            p = points.pop()
            damage_type = random.choice([Tags.Arcane, Tags.Poison])
            self.owner.level.show_effect(p.x, p.y, damage_type, minor=True)
    
    def fallout(target, amount):
        poison = target.get_buff(Poison)
        if not poison:
            target.apply_buff(Poison(), amount)
        else:
            poison.turns_left += amount
    
    def on_death(self, evt):
        poison = self.owner.get_buff(Poison)
        if not poison:
            return
        radius = math.ceil(poison.turns_left/10)
        units = self.owner.level.get_units_in_ball(Point(self.owner.x, self.owner.y), radius)
        units = [unit for unit in units if unit is not self.owner and not are_hostile(self.owner, unit)]
        if not units:
            return
        random.shuffle(units)
        amount = poison.turns_left//len(units)
        self.owner.level.queue_spell(send_bolts(lambda point: self.owner.level.show_effect(point.x, point.y, Tags.Poison), lambda target: IrradiateBuff.fallout(target, amount), self.owner, units))

class IrradiateSpell(Spell):

    def on_init(self):
        self.name = "Irradiate"
        self.asset = ["MissingSynergies", "Icons", "irradiate"]

        self.tags = [Tags.Arcane, Tags.Nature, Tags.Enchantment]
        self.level = 5
        self.max_charges = 7
        self.can_target_self = True

        self.radius = 4
        self.range = 9
        self.duration = 4

        self.upgrades['radius'] = (3, 2)
        self.upgrades['duration'] = (6, 3)
        self.upgrades['fallout'] = (1, 5, "Radioactive Fallout", "When an Irradiated enemy dies, its remaining poison duration is distributed evenly among all enemies in its radiation aura radius, stacking in duration with any pre-existing poisons they have.")

    def get_description(self):
        return ("Irradiates enemies in a [{radius}_tile:radius] radius for [{duration}_turns:duration].\n"
                "An Irradiated target randomly deals [2_arcane:arcane] or [2_poison:poison] damage to all enemies each turn, including itself, in a radius equal to its [poison] duration divided by 10, rounded up.\n"
                "This damage is fixed, and cannot be increased using shrines, skills, or buffs.").format(**self.fmt_dict())

    def cast_instant(self, x, y):
        for p in self.owner.level.get_points_in_ball(x, y, self.get_stat('radius')):
            u = self.owner.level.get_unit_at(p.x, p.y)
            if u and are_hostile(u, self.caster):
                u.apply_buff(IrradiateBuff(self), self.get_stat('duration'))

class ShiveringVenomBuff(Buff):

    def __init__(self, upgrade):
        Buff.__init__(self)
        self.upgrade = upgrade
        self.buff_type = BUFF_TYPE_PASSIVE

    def on_applied(self, owner):
        poison = self.owner.get_buff(Poison)
        if poison:
            self.resists[Tags.Ice] = -poison.turns_left
        else:
            self.resists[Tags.Ice] = 0
        freeze = self.owner.get_buff(FrozenBuff)
        if freeze:
            self.resists[Tags.Poison] = -10*freeze.turns_left
        else:
            self.resists[Tags.Poison] = 0

    def on_advance(self):

        # Remove this if an enemy becomes friendly via Dominate
        if not are_hostile(self.owner, self.upgrade.owner):
            self.owner.remove_buff(self)
            return

        self.owner.resists[Tags.Ice] -= self.resists[Tags.Ice]
        poison = self.owner.get_buff(Poison)
        if poison:
            self.resists[Tags.Ice] = -poison.turns_left
        else:
            self.resists[Tags.Ice] = 0
        self.owner.resists[Tags.Ice] += self.resists[Tags.Ice]
        
        self.owner.resists[Tags.Poison] -= self.resists[Tags.Poison]
        freeze = self.owner.get_buff(FrozenBuff)
        if freeze:
            self.resists[Tags.Poison] = -10*freeze.turns_left
        else:
            self.resists[Tags.Poison] = 0
        self.owner.resists[Tags.Poison] += self.resists[Tags.Poison]

class ShiveringVenom(Upgrade):
    def on_init(self):
        self.name = "Shivering Venom"
        self.asset = ["MissingSynergies", "Icons", "shivering_venom"]
        self.tags = [Tags.Ice, Tags.Nature]
        self.level = 6
        self.global_triggers[EventOnBuffApply] = self.on_buff_apply
        self.description = ("Every enemy has [-1_ice:ice] resistance for each turn of [poison] it has.\n"
                            "Every enemy has [-10_poison:poison] resistance for each turn of [frozen] it has.\n")
    def on_buff_apply(self, evt):
        if not are_hostile(self.owner, evt.unit):
            return
        if isinstance(evt.buff, Poison) or isinstance(evt.buff, FrozenBuff):
            evt.unit.apply_buff(ShiveringVenomBuff(self))

class Electrolysis(Upgrade):

    def on_init(self):
        self.name = "Electrolysis"
        self.asset = ["MissingSynergies", "Icons", "electrolysis"]
        self.tags = [Tags.Lightning, Tags.Nature]
        self.level = 6
        self.duration = 10
        self.radius = 6
        self.global_triggers[EventOnDamaged] = self.on_damaged

    def fmt_dict(self):
        stats = Upgrade.fmt_dict(self)
        stats["total_duration"] = self.get_stat("duration") + self.get_stat("damage")
        return stats

    def get_description(self):
        return ("If a [poisoned:poison] enemy takes [lightning] damage from a source other than this skill, its [poison] duration is reduced by half.\n"
                "For every 10 turns of poison removed, rounded up, a random enemy in a [{radius}_tile:radius] radius is [acidified:poison], losing [100_poison:poison] resistance. An enemy can be targeted multiple times, and the original enemy can also be targeted.\n"
                "If the target enemy is already [acidified:poison], it is instead [poisoned:poison] for [{total_duration}_turns:duration]. This duration benefits from bonuses to both [duration] and [damage].\n"
                "If this would increase its [poison] duration by less than [{total_duration}_turns:duration], the remainder is dealt as [lightning] damage.\n").format(**self.fmt_dict())
    
    def on_damaged(self, evt):
    
        if not are_hostile(self.owner, evt.unit):
            return
        if evt.damage_type != Tags.Lightning:
            return
        if evt.source is self:
            return
        
        poison = evt.unit.get_buff(Poison)
        if not poison:
            return
        amount = poison.turns_left//2
        poison.turns_left -= amount
        radius = self.get_stat('radius')
        duration = self.get_stat("duration") + self.get_stat("damage")
        
        for _ in range(math.ceil(amount/10)):
            targets = [t for t in self.owner.level.get_units_in_ball(evt.unit, radius) if are_hostile(t, self.owner)]
            if not targets:
                return
            self.owner.level.queue_spell(self.electrolyze(evt.unit, random.choice(targets), duration))

    def electrolyze(self, origin, target, duration):
        for point in Bolt(self.owner.level, origin, target):
            self.owner.level.show_effect(point.x, point.y, Tags.Lightning, minor=True)
            self.owner.level.show_effect(point.x, point.y, Tags.Poison, minor=True)
            yield
        if not target.has_buff(Acidified):
            target.apply_buff(Acidified())
        else:
            poison = target.get_buff(Poison)
            if not poison:
                target.apply_buff(Poison(), duration)
            else:
                if poison.turns_left >= duration:
                    target.deal_damage(duration, Tags.Lightning, self)
                else:
                    remainder = duration - poison.turns_left
                    poison.turns_left = duration
                    target.deal_damage(remainder, Tags.Lightning, self)

class FrozenSpaceLeavingArea(Buff):

    def __init__(self, source):
        self.source = source
        Buff.__init__(self)
    
    def on_init(self):
        self.buff_type = BUFF_TYPE_PASSIVE
        self.global_triggers[EventOnMoved] = self.on_moved
        self.prereq = None
    
    def on_moved(self, evt):
        if evt.unit is not self.owner and evt.unit is not self.source.owner:
            return
        if not distance(self.owner, self.source.owner) > self.source.radius:
            return
        if evt.teleport and evt.unit is self.owner and self.source.applied:
            self.source.effect(self.owner)
        self.owner.remove_buff(self)

class FrozenSpaceBuff(Buff):

    def __init__(self, spell):
        self.spell = spell
        Buff.__init__(self)

    def on_init(self):
        self.name = "Frozen Space"
        self.color = Tags.Ice.color
        self.global_triggers[EventOnUnitAdded] = self.on_unit_added
        self.global_triggers[EventOnMoved] = self.on_moved
        self.banishing = self.spell.get_stat("banishing")
        self.shielding = self.spell.get_stat("shielding")
        self.bidirectional = self.spell.get_stat("bidirectional")
        self.damage = self.spell.get_stat("damage")
        self.radius = self.spell.get_stat("radius")
    
    def on_applied(self, owner):
        if self.bidirectional:
            for unit in self.owner.level.get_units_in_ball(self.owner, self.radius):
                unit.apply_buff(FrozenSpaceLeavingArea(self))

    def on_advance(self):
        # Show some graphical indication of this aura
        points = [p for p in self.owner.level.get_points_in_ball(self.owner.x, self.owner.y, self.radius) if not self.owner.level.get_unit_at(p.x, p.y)]
        random.shuffle(points)
        for _ in range(7):
            if not points:
                break
            p = points.pop()
            self.owner.level.show_effect(p.x, p.y, Tags.Ice, minor=True)
    
    def on_moved(self, evt):
        if evt.unit is self.owner:
            self.on_applied(self.owner)
            return
        if distance(evt.unit, self.owner) <= self.radius:
            if evt.teleport:
                self.effect(evt.unit)
            if self.bidirectional:
                evt.unit.apply_buff(FrozenSpaceLeavingArea(self))
    
    def on_unit_added(self, evt):
        if evt.unit is self.owner:
            self.on_applied(self.owner)
            return
        if distance(self.owner, evt.unit) <= self.radius:
            if self.banishing:
                self.effect(evt.unit)
            if self.bidirectional:
                evt.unit.apply_buff(FrozenSpaceLeavingArea(self))
    
    def effect(self, unit):
        if unit is self.owner:
            return
        if not are_hostile(unit, self.owner):
            if self.shielding and unit.shields < 3:
                unit.add_shields(1)
            return
        unit.deal_damage(self.damage, Tags.Ice, self.spell)
        unit.apply_buff(FrozenBuff(), 3)

class FrozenSpaceSpell(Spell):

    def on_init(self):
        self.name = "Frozen Space"
        self.asset = ["MissingSynergies", "Icons", "frozen_space"]

        self.range = 0
        self.max_charges = 3
        self.damage = 7
        self.radius = 7
        self.duration = 30

        self.upgrades['radius'] = (3, 2)
        self.upgrades['damage'] = (5, 3)
        self.upgrades['bidirectional'] = (1, 3, "Bidirectional", "Also works on units teleporting out of this spell's area of effect.")
        self.upgrades['banishing'] = (1, 5, "Banishing", "Also works on units summoned inside this spell's area of effect.")
        self.upgrades['shielding'] = (1, 3, "Shielding Space", "Also affects your minions, giving them [1_SH:shields] instead on activation, up to a max of [3_SH:shield].")

        self.tags = [Tags.Enchantment, Tags.Ice, Tags.Translocation]
        self.level = 3

    def get_description(self):
        return ("Whenever an enemy teleports to anywhere within [{radius}_tiles:radius] of you, that enemy takes [{damage}_ice:ice] damage and is [frozen] for [3_turns:duration].\n"
                "Lasts [{duration}_turns:duration].").format(**self.fmt_dict())
    
    def cast_instant(self, x, y):
        self.caster.apply_buff(FrozenSpaceBuff(self), self.get_stat('duration'))

class WildHuntBuff(Buff):

    def __init__(self, spell):
        self.spell = spell
        Buff.__init__(self)

    def on_init(self):
        self.name = "Wild Hunt"
        self.color = Tags.Nature.color
        self.asset = ["MissingSynergies", "Statuses", "wild_hunt"]
    
    def qualifies(self, unit):
        if unit is self.spell.caster:
            return False
        if unit.team != TEAM_PLAYER:
            return False
        if Tags.Living in unit.tags or Tags.Nature in unit.tags:
            return True
        if self.spell.get_stat("holy_units") and Tags.Holy in unit.tags:
            return True
        if self.spell.get_stat("demon_units") and Tags.Demon in unit.tags:
            return True
        if self.spell.get_stat("undead_units") and Tags.Undead in unit.tags:
            return True
        return False
    
    def do_teleport(self, units):
        units_teleported = 0
        for unit in units:
            if units_teleported >= self.spell.get_stat("num_targets"):
                return
            if self.qualifies(unit):
                point = self.owner.level.get_summon_point(self.owner.x, self.owner.y, flying=unit.flying)
                if point:
                    units_teleported += 1
                    yield self.owner.level.act_move(unit, point.x, point.y, teleport=True)
                    self.owner.level.show_effect(unit.x, unit.y, Tags.Translocation)
    
    def on_advance(self):
        units = self.owner.level.units
        random.shuffle(units)
        self.owner.level.queue_spell(self.do_teleport(units))

class WildHuntSpell(Spell):

    def on_init(self):
        self.name = "Wild Hunt"
        self.asset = ["MissingSynergies", "Icons", "wild_hunt"]
        
        self.tags = [Tags.Enchantment, Tags.Nature, Tags.Translocation]
        self.level = 4
        self.max_charges = 3
        self.range = 10
        self.duration = 8
        self.num_targets = 3
        self.can_target_self = True
        self.can_target_empty = False
        
        self.upgrades["duration"] = (8, 2)
        self.upgrades["num_targets"] = (2, 2, "Num Targets", "[2:num_targets] more minions are teleported to the target each turn.")
        self.upgrades["requires_los"] = (-1, 2, "Blindcasting", "Wild Hunt can be cast without line of sight.")
        self.upgrades["holy_units"] = (1, 2, "Holy Crusade", "Can also teleport [holy] minions.")
        self.upgrades["demon_units"] = (1, 1, "Infernal Legion", "Can also teleport [demon] minions.")
        self.upgrades["undead_units"] = (1, 1, "Undead Horde", "Can also teleport [undead] minions.")
    
    def get_description(self):
        return ("For [{duration}_turns:duration], the target has [{num_targets}:num_targets] of your [living] or [nature] minions randomly teleported next to it each turn.").format(**self.fmt_dict())
    
    def cast_instant(self, x, y):
        unit = self.caster.level.get_unit_at(x, y)
        if unit:
            buff = WildHuntBuff(self)
            if are_hostile(unit, self.caster):
                buff.buff_type = BUFF_TYPE_CURSE
            unit.apply_buff(buff, self.get_stat("duration"))

class PlanarBindingBuff(Buff):
    
    def __init__(self, spell, x, y):
        self.spell = spell
        self.x = x
        self.y = y
        Buff.__init__(self)

    def on_init(self):
        self.name = "Planar Binding"
        self.color = Tags.Holy.color
        self.buff_type = BUFF_TYPE_CURSE
        self.asset = ["MissingSynergies", "Statuses", "planar_binding"]
        if self.spell.get_stat("thorough"):
            self.owner_triggers[EventOnMoved] = self.on_moved
    
    def do_teleport(self):
    
        if self.owner.x != self.x or self.owner.y != self.y:
            point = self.owner.level.get_summon_point(self.x, self.y, flying=self.owner.flying)
            if point:
                # Prevent infinite loop with Thorough Binding if the original location is blocked
                self.x = point.x
                self.y = point.y
                self.owner.level.show_effect(self.owner.x, self.owner.y, Tags.Translocation)
                self.owner.level.act_move(self.owner, point.x, point.y, teleport=True)
            return
        
        # We can't actually teleport the unit onto the same tile as itself, because that tile is occupied by itself
        # So we just cheat, raise an EventOnMoved, and pretend the teleport happened
        if self.spell.get_stat("redundancy") and self.owner.is_alive():
            self.owner.level.event_manager.raise_event(EventOnMoved(self.owner, self.x, self.y, teleport=True), self.owner)
            self.owner.level.show_effect(self.owner.x, self.owner.y, Tags.Translocation)

    def on_advance(self):
        self.do_teleport()
    
    def on_moved(self, evt):
        if not evt.teleport:
            return
        self.do_teleport()

class PlanarBindingSpell(Spell):

    def on_init(self):
        self.name = "Planar Binding"
        self.asset = ["MissingSynergies", "Icons", "planar_binding"]
        
        self.tags = [Tags.Enchantment, Tags.Holy, Tags.Translocation]
        self.level = 3
        self.max_charges = 6
        self.range = 8
        self.duration = 5
        self.can_target_self = True
        self.can_target_empty = False
        
        self.upgrades["duration"] = (10, 3)
        self.upgrades["range"] = (7, 2)
        self.upgrades["requires_los"] = (-1, 2, "Blindcasting", "Planar Binding can be cast without line of sight.")
        self.upgrades["redundancy"] = (1, 2, "Redundancy", "The target still counts as having teleported even if it did not move away from its original spot.")
        self.upgrades["thorough"] = (1, 5, "Thorough Binding", "The target will now be immediately teleported back to its original location whenever it teleports.")
    
    def get_description(self):
        return ("For [{duration}_turns:duration], the target will be teleported back each turn to the location it was when this spell was originally cast if it moved away from that tile.").format(**self.fmt_dict())

    def cast_instant(self, x, y):
        unit = self.caster.level.get_unit_at(x, y)
        if unit:
            unit.apply_buff(PlanarBindingBuff(self, x, y), self.get_stat("duration"))

class ChaosShuffleSpell(Spell):

    def on_init(self):
        self.name = "Chaos Shuffle"
        self.asset = ["MissingSynergies", "Icons", "chaos_shuffle"]
        
        self.tags = [Tags.Sorcery, Tags.Chaos, Tags.Translocation]
        self.level = 3
        self.max_charges = 8
        self.range = 8
        self.damage = 12
        self.num_targets = 3
        self.can_target_empty = False
        
        self.upgrades["requires_los"] = (-1, 2, "Blindcasting", "Chaos Shuffle can be cast without line of sight.")
        self.upgrades["max_charges"] = (4, 2)
        self.upgrades["num_targets"] = (2, 2, "Num Targets", "Shuffle the target [2:num_targets] more times.")
        self.upgrades["mass"] = (1, 5, "Mass Shuffle", "Each time the main target is shuffled, all enemies within [3_tiles:radius] of it are shuffled once.")
        
    def get_description(self):
        return ("The target is teleported [{num_targets}:num_targets] times consecutively up to [3_tiles:radius] away each time, taking [{damage}_fire:fire], [{damage}_lightning:lightning], or [{damage}_physical:physical] damage after each teleport.").format(**self.fmt_dict())

    def shuffle_once(self, unit):
        randomly_teleport(unit, 3)
        unit.deal_damage(self.get_stat("damage"), random.choice([Tags.Fire, Tags.Lightning, Tags.Physical]), self)
    
    def shuffle(self, unit):
        self.shuffle_once(unit)
        if not self.get_stat("mass"):
            yield False
        others = self.owner.level.get_units_in_ball(Point(unit.x, unit.y), self.get_stat("radius", base=3))
        others = [other for other in others if other is not unit and are_hostile(self.caster, other)]
        random.shuffle(others)
        for other in others:
            self.shuffle_once(other)
            yield True
        yield False
    
    def cast(self, x, y):
        unit = self.caster.level.get_unit_at(x, y)
        if unit:
            for _ in range(self.get_stat("num_targets")):
                shuffling = self.shuffle(unit)
                while next(shuffling):
                    yield
                yield

class BladeRushSpell(Spell):

    def on_init(self):
        self.name = "Blade Rush"
        self.asset = ["MissingSynergies", "Icons", "blade_rush"]
        
        self.tags = [Tags.Sorcery, Tags.Metallic, Tags.Translocation]
        self.level = 3
        self.max_charges = 7
        self.range = 15
        self.damage = 16
        
        self.upgrades["range"] = (5, 2)
        self.upgrades["max_charges"] = (4, 3)
        self.upgrades["dark"] = (1, 4, "Death Blade", "Blade Rush also deals [dark] damage. Automatically cast your Touch of Death at the target after teleporting.", "blade")
        self.upgrades["lightning"] = (1, 4, "Thunder Blade", "Blade Rush also deals [lightning] damage.Automatically cast your Thunder Strike at the target after teleporting.", "blade")
        self.upgrades["arcane"] = (1, 4, "Warp Blade", "Blade Rush also deals [arcane] damage. Automatically cast your Disperse at the target after teleporting.", "blade")
        self.upgrades["motivation"] = (1, 4, "Motivation", "If you target a tile adjacent to yourself, you will create [6:num_targets] to [12:num_targets] slashes around the target tile in a radius equal to half of this spell's range, each dealing the same damage and damage types; they will not damage you.\nThe number of slashes benefits from bonuses to [num_targets:num_targets].")
    
    def get_description(self):
        return ("Dash in a line, dealing [{damage}:physical] damage to all tiles you pass through and the target tile.\n"
                "You stop at the tile in the line immediately before the target; cannot cast if you cannot walk on that tile.").format(**self.fmt_dict())

    def can_cast(self, x, y):
        if not Spell.can_cast(self, x, y):
            return False

        point = self.caster.level.get_points_in_line(self.caster, Point(x, y))[-2]
        return self.caster.level.can_move(self.caster, point.x, point.y, teleport=True) if point != Point(self.caster.x, self.caster.y) else True
    
    def get_impacted_tiles(self, x, y):
        return self.caster.level.get_points_in_line(self.caster, Point(x, y))
    
    def cast(self, x, y):
    
        path = self.caster.level.get_points_in_line(self.caster, Point(x, y))
        dest = path[-2]
        if dest != Point(self.caster.x, self.caster.y) and not self.caster.level.can_move(self.caster, dest.x, dest.y, teleport=True):
            return

        dtypes = [Tags.Physical]
        spell = None
        if self.get_stat("dark"):
            dtypes.append(Tags.Dark)
            spell = TouchOfDeath()
        if self.get_stat("lightning"):
            dtypes.append(Tags.Lightning)
            spell = ThunderStrike()
        if self.get_stat("arcane"):
            dtypes.append(Tags.Arcane)
            spell = DispersalSpell()
        if spell:
            spell.statholder = self.caster
            spell.caster = self.caster
            spell.owner = self.caster
        
        damage = self.get_stat("damage")
        
        target = Point(x, y)
        if self.get_stat("motivation") and target in self.caster.level.get_adjacent_points(Point(self.caster.x, self.caster.y), filter_walkable=False):
            radius = self.get_stat("range")//2
            ring = [point for point in self.caster.level.get_points_in_ball(target.x, target.y, radius) if distance(point, target) >= radius - 1]
            if ring:
                num_targets = self.get_stat("num_targets", base=6)
                for _ in range(random.choice(list(range(num_targets, num_targets*2 + 1)))):
                    start = random.choice(ring)
                    end = random.choice(ring)
                    for point in self.caster.level.get_points_in_line(start, end):
                        if point.x == self.caster.x and point.y == self.caster.y:
                            for dtype in dtypes:
                                self.caster.level.show_effect(point.x, point.y, dtype)
                        else:
                            for dtype in dtypes:
                                self.caster.level.deal_damage(point.x, point.y, damage, dtype, self)
                        yield
        
        self.caster.invisible = True
        if dest != Point(self.caster.x, self.caster.y):
            self.caster.level.act_move(self.caster, dest.x, dest.y, teleport=True)
        for point in path[1:-2]:
            self.caster.level.leap_effect(point.x, point.y, Tags.Metallic.color, self.caster)
            for dtype in dtypes:
                self.caster.level.deal_damage(point.x, point.y, damage, dtype, self)
            yield
        self.caster.invisible = False
        for dtype in dtypes:
            self.caster.level.deal_damage(x, y, damage, dtype, self)
        if spell:
            self.caster.level.act_cast(self.caster, spell, x, y, pay_costs=False)

class MaskOfTroublesBuff(Buff):

    def __init__(self, spell):
        self.spell = spell
        Buff.__init__(self)
    
    def on_init(self):
        self.name = "Mask of Troubles"
        self.color = Tags.Arcane.color
        self.stack_type = STACK_TYPE_TRANSFORM
        self.transform_asset_name = os.path.join("..", "..", "mods", "MissingSynergies", "Units", "mask_of_troubles")
        self.resists[Tags.Arcane] = 100
        self.resists[Tags.Poison] = 100
        self.owner_triggers[EventOnMoved] = self.on_moved
        self.asset = ["MissingSynergies", "Statuses", "mask_of_troubles"]
    
    def on_moved(self, evt):
        if evt.teleport:
            self.spell.summon(self.get_troubler(), radius=5, sort_dist=False)
    
    def get_troubler(self, baby=False):
        if not baby:
            unit = Troubler()
        else:
            unit = TroublerTiny()
        apply_minion_bonuses(self.spell, unit)
        unit.shields += self.spell.get_stat("shields")
        if self.spell.get_stat("endless") and not baby:
            unit.buffs.append(RespawnAs(lambda: self.get_troubler(baby=True)))
        elif baby:
            buff = unit.get_buff(MatureInto)
            if buff:
                buff.spawner = lambda: self.get_troubler()
        unit.source = self.spell
        return unit
    
    def do_teleport(self):
        if not self.spell.get_stat("stability"):
            yield randomly_teleport(self.owner, 3)
        else:
            yield self.owner.level.event_manager.raise_event(EventOnMoved(self.owner, self.owner.x, self.owner.y, teleport=True), self.owner)
            self.owner.level.show_effect(self.owner.x, self.owner.y, Tags.Translocation)
    
    def on_advance(self):
        self.owner.level.queue_spell(self.do_teleport())

class MaskOfTroublesSpell(Spell):

    def on_init(self):
        self.name = "Mask of Troubles"
        self.asset = ["MissingSynergies", "Icons", "mask_of_troubles"]
        
        self.tags = [Tags.Conjuration, Tags.Enchantment, Tags.Translocation, Tags.Arcane]
        self.level = 5
        self.max_charges = 2
        self.duration = 8
        self.range = 0
        
        self.minion_health = 1
        self.minion_damage = 2
        self.minion_range = 10
        self.shields = 0
        
        self.upgrades["duration"] = (10, 4)
        self.upgrades["stability"] = (1, 2, "Stability", "You no longer randomly teleport for the duration, but still count as having teleported 1 extra time per turn.")
        self.upgrades["shields"] = (3, 2, "Shields", "Summoned troublers have an additional [3_SH:shields].")
        self.upgrades["endless"] = (1, 2, "Endless Troubles", "Summoned troublers respawn as baby troublers on death.")
    
    def get_description(self):
        return ("Put on the Mask of Troubles for [{duration}_turns:duration], gaining the following benefits:\n"
                "Gain [100_poison:poison] and [100_arcane:arcane] resist.\n"
                "Each turn, teleport to a random location up to [3_tiles:radius] away.\n"
                "Whenever you teleport, summon a friendly troubler nearby.\n"
                "Troublers have low health and damage, but long range, and randomly teleport enemies with their attacks.").format(**self.fmt_dict())
    
    def cast_instant(self, x, y):
        self.caster.apply_buff(MaskOfTroublesBuff(self), self.get_stat("duration"))

class BombasticArrival(Upgrade):

    def on_init(self):
        self.name = "Bombastic Arrival"
        self.asset = ["MissingSynergies", "Icons", "bombastic_arrival"]
        
        self.tags = [Tags.Translocation, Tags.Fire]
        self.level = 5
        self.damage = 12
        self.radius = 3
        self.owner_triggers[EventOnMoved] = self.on_moved
    
    def get_description(self):
        return ("Whenever you teleport, deal [{damage}_fire:fire] damage in a [{radius}_tile:radius] burst on arrival. Allies are unaffected.").format(**self.fmt_dict())
    
    def boom(self):
        for stage in Burst(self.owner.level, Point(self.owner.x, self.owner.y), self.get_stat("radius")):
            for point in stage:
                unit = self.owner.level.get_unit_at(point.x, point.y)
                if unit and not are_hostile(self.owner, unit):
                    self.owner.level.show_effect(point.x, point.y, Tags.Fire)
                else:
                    self.owner.level.deal_damage(point.x, point.y, self.get_stat("damage"), Tags.Fire, self)
            yield
    
    def on_moved(self, evt):
        if evt.teleport:
            self.owner.level.queue_spell(self.boom())

class ShadowAssassin(Upgrade):

    def on_init(self):
        self.name = "Shadow Assassin"
        self.asset = ["MissingSynergies", "Icons", "shadow_assassin"]
        
        self.tags = [Tags.Translocation, Tags.Dark]
        self.level = 4
        self.damage = 12
        self.owner_triggers[EventOnMoved] = self.on_moved
    
    def on_applied(self, owner):
        # Initialize old position
        self.old_x = self.owner.x
        self.old_y = self.owner.y
    
    def get_description(self):
        return ("Whenever you teleport, if there is only a single enemy adjacent to you on arrival, deal [{damage}_dark:dark], [{damage}_physical:physical], and [{damage}_poison:poison] damage to it.\n"
                "If you teleported to that enemy from out of line of sight or at least [8_tiles:range] away, or the enemy is [blind], deal double damage.").format(**self.fmt_dict())
    
    def on_moved(self, evt):
        
        if evt.teleport:
    
            enemy_count = 0
            points = self.owner.level.get_adjacent_points(self.owner)
            target = None
            for point in points:
                unit = self.owner.level.get_unit_at(point.x, point.y)
                if unit and are_hostile(unit, self.owner):
                    enemy_count += 1
                    if enemy_count > 1:
                        return
                    target = unit
            if not target:
                return
            
            damage = self.get_stat("damage")
            if target.has_buff(BlindBuff) or not self.owner.level.can_see(target.x, target.y, self.old_x, self.old_y) or distance(target, Point(self.old_x, self.old_y)) >= 8:
                damage *= 2
            for dtype in [Tags.Dark, Tags.Physical, Tags.Poison]:
                target.deal_damage(damage, dtype, self)

        self.old_x = self.owner.x
        self.old_y = self.owner.y

class PrismShellBuff(Buff):
    def __init__(self, spell):
        self.spell = spell
        Buff.__init__(self)
    
    def on_init(self):
        self.name = "Prism Shell"
        self.color = Tags.Ice.color
        self.owner_triggers[EventOnPreDamaged] = self.on_pre_damaged
        self.owner_triggers[EventOnDamaged] = self.on_damaged
        self.asset = ["MissingSynergies", "Statuses", "prism_shell"]
    
    def get_targets(self):
        targets = self.owner.level.get_units_in_ball(self.owner, self.spell.get_stat("radius"))
        targets = [t for t in targets if are_hostile(t, self.owner) and self.owner.level.can_see(t.x, t.y, self.owner.x, self.owner.y)]
        random.shuffle(targets)
        return targets[:self.spell.get_stat("num_targets")]
    
    def on_damaged(self, evt):
        target_effect = lambda target: target.deal_damage(evt.damage, Tags.Holy, self.spell)
        path_effect = lambda point: self.owner.level.show_effect(point.x, point.y, Tags.Holy)
        self.owner.level.queue_spell(send_bolts(path_effect, target_effect, self.owner, self.get_targets()))
    
    def on_pre_damaged(self, evt):
        if evt.damage <= 0 or not evt.unit.shields or self.owner.resists[evt.damage_type] >= 100:
            return
        target_effect = lambda target: target.apply_buff(FrozenBuff(), 3)
        path_effect = lambda point: self.owner.level.show_effect(point.x, point.y, Tags.Ice)
        self.owner.level.queue_spell(send_bolts(path_effect, target_effect, self.owner, self.get_targets()))
    
    def on_advance(self):
        if self.owner.shields < self.spell.get_stat("shield_max"):
            self.owner.add_shields(self.spell.get_stat("shield_amount"))
            self.owner.shields = min(self.owner.shields, self.spell.get_stat("shield_max"))
        if self.spell.get_stat("cleanse"):
            debuffs = [buff for buff in self.owner.buffs if buff.buff_type == BUFF_TYPE_CURSE]
            if debuffs:
                self.owner.remove_buff(random.choice(debuffs))

class PrismShellSpell(Spell):
    
    def on_init(self):
        self.name = "Prism Shell"
        self.asset = ["MissingSynergies", "Icons", "prism_shell"]
        
        self.tags = [Tags.Enchantment, Tags.Ice, Tags.Holy]
        self.level = 4
        self.max_charges = 5
        self.range = 5
        self.duration = 10
        self.radius = 5
        self.num_targets = 2
        self.shield_max = 3
        self.shield_amount = 1
        self.can_target_empty = False
        
        self.upgrades["num_targets"] = (2, 3, "Num Targets", "[2:num_targets] more enemies are affected by [freeze] and [holy] damage.")
        self.upgrades["shield_max"] = (2, 3)
        self.upgrades["shield_amount"] = (1, 3)
        self.upgrades["cleanse"] = (1, 2, "Pure Ice", "Also removes 1 random debuff per turn.")
    
    def get_description(self):
        return ("Target minion gains [{shield_amount}_SH:shields] per turn, up to a max of [{shield_max}_SH:shields].\n"
                "Whenever it loses [SH:shields], [freeze] [{num_targets}:num_targets] random enemies in a [{radius}_tile:radius] burst for [3_turns:duration].\n"
                "Whenever it takes damage, deal [holy] damage to [{num_targets}:num_targets] random enemies in a [{radius}_tile:radius] burst equal to the damage taken.\n"
                "Lasts [{duration}_turns:duration].").format(**self.fmt_dict())
    
    def can_cast(self, x, y):
        unit = self.caster.level.get_unit_at(x, y)
        if unit and are_hostile(unit, self.caster):
            return False
        return Spell.can_cast(self, x, y)
    
    def cast_instant(self, x, y):
        unit = self.caster.level.get_unit_at(x, y)
        if unit:
            unit.apply_buff(PrismShellBuff(self), self.get_stat("duration"))

class CrystalHammerSpell(Spell):

    def on_init(self):
        self.name = "Crystal Hammer"
        self.asset = ["MissingSynergies", "Icons", "crystal_hammer"]
        
        self.tags = [Tags.Sorcery, Tags.Ice, Tags.Metallic]
        self.level = 5
        self.max_charges = 3
        self.range = 5
        self.damage = 50
        self.extra_damage = 10
        self.can_target_empty = False
        
        self.upgrades["damage"] = (50, 2)
        self.upgrades["extra_damage"] = (5, 3, "Extra Damage", "+5 extra damage per turn of [freeze] and [glassify].")
        self.upgrades["shatter"] = (1, 6, "Shatter", "If the target is killed, release a number of shards equal to the number of turns of frozen and glassify on the target plus 1 per 20 max HP the target had, rounded up.\nEach shard targets a random enemy in a [6_tile:radius] burst and deals [physical] damage equal to this spell's extra damage.\nThe same enemy can be hit more than once.")
    
    def get_description(self):
        return ("Deal [{damage}_physical:physical] damage to the target. For every turn of [freeze] and [glassify] on the target, deal [{extra_damage}:physical] extra damage. Remove all [freeze] and [glassify] on the target afterwards.").format(**self.fmt_dict())
    
    def cast_instant(self, x, y):
    
        unit = self.caster.level.get_unit_at(x, y)
        if not unit:
            return
        
        total_duration = 0
        freeze = unit.get_buff(FrozenBuff)
        if freeze:
            total_duration += freeze.turns_left
        glassify = unit.get_buff(GlassPetrifyBuff)
        if glassify:
            total_duration += glassify.turns_left
        extra_damage = self.get_stat("extra_damage")
        unit.deal_damage(self.get_stat("damage") + total_duration*extra_damage, Tags.Physical, self)
        if unit.is_alive():
            if glassify:
                unit.remove_buff(glassify)
            return
        
        if self.get_stat("shatter"):
            radius = self.get_stat("radius", base=6)
            for _ in range(total_duration + math.ceil(unit.max_hp/20)):
                targets = self.caster.level.get_units_in_ball(unit, radius)
                targets = [t for t in targets if are_hostile(t, self.caster) and self.caster.level.can_see(t.x, t.y, unit.x, unit.y)]
                if not targets:
                    return
                self.caster.level.queue_spell(self.bolt(unit, random.choice(targets), extra_damage))

    def bolt(self, origin, target, damage):
        for point in Bolt(self.caster.level, origin, target):
            self.caster.level.show_effect(point.x, point.y, Tags.Physical, minor=True)
            yield
        target.deal_damage(damage, Tags.Physical, self)

class ReturningArrowBuff(Buff):

    def __init__(self, spell):
        self.spell = spell
        Buff.__init__(self)
    
    def on_init(self):
        self.name = "Returning Arrow"
        self.color = Tags.Arcane.color
        self.buff_type = BUFF_TYPE_CURSE
        self.stack_type = STACK_INTENSITY
        self.damage = self.spell.get_stat("damage")
        self.cursing = False
        if self.spell.get_stat("cursing"):
            self.cursing = True
            self.resists[Tags.Dark] = -25
        if self.spell.get_stat("recalling"):
            self.owner_triggers[EventOnDamaged] = self.on_damaged
        self.asset = ["MissingSynergies", "Statuses", "returning_arrow"]
    
    def on_damaged(self, evt):
        if evt.damage_type == Tags.Holy:
            self.owner.remove_buff(self)
    
    def on_advance(self):
        if self.cursing:
            self.owner.deal_damage(self.damage, Tags.Dark, self.spell)
    
    def on_unapplied(self):
        self.owner.level.queue_spell(self.spell.arrow(self.owner, self.spell.caster, returning=True))

class ReturningArrowSpell(Spell):

    def on_init(self):
        self.name = "Returning Arrow"
        self.asset = ["MissingSynergies", "Icons", "returning_arrow"]
        
        self.tags = [Tags.Sorcery, Tags.Arcane, Tags.Metallic]
        self.level = 4
        self.max_charges = 6
        self.range = 10
        self.damage = 8
        self.can_target_empty = False
        
        self.upgrades["requires_los"] = (-1, 5, "Phasing Arrow", "The arrow can now pass through walls.")
        self.upgrades["recalling"] = (1, 3, "Recalling Arrow", "If a enemy with arrows embedded in it takes [holy] damage, all arrows rip themselves free immediately, damaging the enemy again and trying to return to you.")
        self.upgrades["cursing"] = (1, 4, "Cursing Arrow", "Each embedded arrow causes the victim to lose [25_dark:dark] resistance and take [dark] damage per turn equal to this spell's damage stat.")
        self.upgrades["arcane"] = (1, 6, "Void Arrow", "Returning Arrow also deals [arcane] damage.")
    
    def get_description(self):
        return ("Deal [{damage}_physical:physical] damage in a line and embed the arrow in the target enemy. Multiple arrows can be embedded at once.\n"
                "When that enemy dies, the arrow tries to return to you, dealing the same damage in a line. If it reaches you, you regain a charge of this spell.\n"
                "This spell does not damage friendly units.").format(**self.fmt_dict())

    def can_cast(self, x, y):
        if not Spell.can_cast(self, x, y):
            return False
        if not are_hostile(self.caster.level.get_unit_at(x, y), self.caster):
            return False
        return True

    def get_impacted_tiles(self, x, y):
        return list(Bolt(self.caster.level, self.caster, Point(x, y), find_clear=False))

    def arrow(self, origin, target, returning=False):
        
        path = self.caster.level.get_points_in_line(origin, target)
        arrow_range = self.get_stat("range")
        requires_los = self.get_stat("requires_los")
        max_charges = self.get_stat("max_charges")
        damage = self.get_stat("damage")
        arcane = self.get_stat("arcane")
        
        for point in path:
        
            if distance(point, origin) > arrow_range:
                return
            if self.caster.level.tiles[point.x][point.y].is_wall() and requires_los:
                return
        
            unit = self.caster.level.get_unit_at(point.x, point.y)
            
            if unit is self.caster:
                if returning and self.cur_charges < max_charges:
                    self.cur_charges += 1
                    self.caster.level.show_effect(point.x, point.y, Tags.Buff_Apply, Tags.Metallic.color)
                yield
                continue
            
            if unit and not are_hostile(self.caster, unit):
                self.caster.level.show_effect(point.x, point.y, Tags.Physical)
                if arcane:
                    self.caster.level.show_effect(point.x, point.y, Tags.Arcane)
                yield
                continue
            
            self.caster.level.deal_damage(point.x, point.y, damage, Tags.Physical, self)
            if arcane:
                self.caster.level.deal_damage(point.x, point.y, damage, Tags.Arcane, self)
            
            # Cannot target empty or allies, so the unit at the target must be the final enemy hit if this is not a returning shot
            if not returning and point is path[-1]:
                if unit and unit.is_alive():
                    unit.apply_buff(ReturningArrowBuff(self))
                else:
                    if not all(u.team == TEAM_PLAYER for u in self.caster.level.units):
                        self.caster.level.queue_spell(self.arrow(point, self.caster, returning=True))
                    else:
                        if self.cur_charges < max_charges:
                            self.cur_charges += 1
                            self.caster.level.show_effect(self.caster.x, self.caster.y, Tags.Buff_Apply, Tags.Metallic.color)
            
            yield
    
    def cast(self, x, y):
        yield from self.arrow(self.caster, Point(x, y))

class PermaBerserkBuff(BerserkBuff):
    def __init__(self):
        BerserkBuff.__init__(self)
        self.name = "Irremovable Berserk"
    def on_unapplied(self):
        self.owner.apply_buff(PermaBerserkBuff())

class WordOfDetonationSpell(Spell):

    def on_init(self):
        self.name = "Word of Detonation"
        self.asset = ["MissingSynergies", "Icons", "word_of_detonation"]
        
        self.tags = [Tags.Fire, Tags.Arcane, Tags.Word]
        self.level = 7
        self.max_charges = 1
        self.range = 0

        self.upgrades["max_charges"] = (1, 2)
        self.upgrades["greater"] = (1, 4, "Greater Detonation", "Chance to instead summon a giant bomber, equal to each target's max HP, up to 100%.")
    
    def get_description(self):
        return ("Summon a fire bomber or void bomber next to every unit except the caster.\n"
                "The bombers are hostile and permanently [berserked:berserk].").format(**self.fmt_dict())
    
    def get_impacted_tiles(self, x, y):
        return [u for u in self.owner.level.units if u is not self.caster]
    
    def cast(self, x, y):

        units = list(self.caster.level.units)
        random.shuffle(units)

        for unit in units:

            if unit is self.caster:
                continue
            
            if self.get_stat("greater") and random.random() < min(unit.max_hp/100, 1):
                bomber_type = random.choice([FireBomberGiant, VoidBomberGiant])
            else:
                bomber_type = random.choice([FireBomber, VoidBomber])
            
            bomber = bomber_type()
            self.summon(bomber, target=unit, team=TEAM_ENEMY, radius=5)
            bomber.apply_buff(PermaBerserkBuff())

            yield

class WordOfUpheavalSpell(Spell):

    def on_init(self):
        self.name = "Word of Upheaval"
        self.asset = ["MissingSynergies", "Icons", "word_of_upheaval"]
        
        self.tags = [Tags.Nature, Tags.Word]
        self.level = 7
        self.max_charges = 1
        self.range = 0
        self.damage = 45

        self.minion_damage = 12
        self.minion_health = 25

        self.upgrades["max_charges"] = (1, 2)
        self.upgrades["damage"] = (20, 2)
        self.upgrades["hallow"] = (1, 5, "Hallowed Earth", "50% chance for each summoned earth elemental to instead be a hallowed earth elemental that is friendly and not berserked.\n")
    
    def get_description(self):
        return ("Each unit that isn't [living] or [nature] has a 50% chance to take [{damage}_physical:physical] damage.\n"
                "Each empty floor tile has a 25% chance to have an earth elemental summoned onto it. The elemental is hostile and permanently [berserked:berserk].\n"
                "Turn all chasms into floors.\n"
                "Turn all walls into chasms.").format(**self.fmt_dict())
    
    def get_impacted_tiles(self, x, y):
        return list(self.caster.level.iter_tiles())
    
    def cast_instant(self, x, y):

        earth_summon = WizardEarthEle()
        # Dummy caster to make the earth elementals start out hostile and not benefit from skills
        dummy_caster = Unit()
        dummy_caster.level = self.caster.level
        earth_summon.caster = dummy_caster

        for tile in self.caster.level.iter_tiles():
                
            unit = self.caster.level.get_unit_at(tile.x, tile.y)

            if unit:
                if Tags.Living not in unit.tags and Tags.Nature not in unit.tags and random.random() < 0.5:
                    self.caster.level.deal_damage(tile.x, tile.y, self.get_stat("damage"), Tags.Physical, self)
                continue
            
            if self.caster.level.can_walk(tile.x, tile.y) and random.random() < 0.25:
                if self.get_stat("hallow") and random.random() < 0.5:
                    elemental = HolyEarthElemental()
                    apply_minion_bonuses(self, elemental)
                    self.summon(elemental, target=tile)
                else:
                    earth_summon.cast_instant(tile.x, tile.y)
                    elemental = self.caster.level.get_unit_at(tile.x, tile.y)
                    if elemental:
                        elemental.apply_buff(PermaBerserkBuff())
                        elemental.turns_to_death = None
            
            if tile.is_chasm:
                self.caster.level.make_floor(tile.x, tile.y)
            
            if tile.is_wall():
                self.caster.level.make_chasm(tile.x, tile.y)

class RaiseDracolichBreath(BreathWeapon):

    def __init__(self, damage, range, legacy):
        self.legacy = legacy
        BreathWeapon.__init__(self)
        self.damage = damage
        self.range = range
        self.damage_type = Tags.Dark

    def on_init(self):
        self.name = "Dark Breath"
        self.description = "Deals Dark damage%s in a cone. Reanimates slain living units as skeletons." % ((" and half %s damage" % self.legacy.name) if self.legacy else "")

    def can_redeal(self, target):
        return self.legacy and not is_immune(target, self, self.legacy)

    def cast(self, x, y):
        if self.legacy:
            # Make Scalespinner count the legacy element too
            dummy_breath = BreathWeapon()
            dummy_breath.damage_type = self.legacy
            dummy_breath.range = self.range
            dummy_breath.damage = 0
            dummy_breath.caster = self.caster
            self.caster.level.event_manager.raise_event(EventOnSpellCast(dummy_breath, self.caster, x, y), self.caster)
        self.caster.level.queue_spell(BreathWeapon.cast(self, x, y))
        yield

    def per_square_effect(self, x, y):
        unit = self.caster.level.get_unit_at(x, y)
        
        self.caster.level.deal_damage(x, y, self.get_stat("damage"), Tags.Dark, self)
        if self.legacy:
            self.caster.level.deal_damage(x, y, self.get_stat("damage")//2, self.legacy, self)

        if unit and not unit.is_alive():
            skeleton = mods.BugsAndScams.Bugfixes.raise_skeleton(self.caster, unit, source=self.caster.source, summon=False)
            if not skeleton:
                return
            skeleton.spells[0].damage = self.caster.source.get_stat("minion_damage", base=skeleton.spells[0].damage)
            summoned = self.caster.source.summon(skeleton, target=unit, radius=0)
            if summoned and self.legacy:
                sorcery = TouchedBySorcery(self.legacy)
                # Gotta do this otherwise the game crashes due to some variants of this buff not having assets
                if self.legacy in [Tags.Fire, Tags.Ice, Tags.Lightning, Tags.Poison, Tags.Arcane, Tags.Physical, Tags.Holy, Tags.Dark]:
                    sorcery.asset = ["MissingSynergies", "Statuses", "%s_eye" % self.legacy.name.lower()]
                else:
                    sorcery.asset = None
                skeleton.apply_buff(sorcery)

class RaiseDracolichSoulJar(LichSealSoulSpell):

    def __init__(self, legacy):
        LichSealSoulSpell.__init__(self)
        self.legacy = legacy

    def cast_instant(self, x, y):

        phylactery = Unit()
        phylactery.name = 'Soul Jar'
        phylactery.max_hp = self.caster.source.get_stat("minion_health", base=6)
        phylactery.stationary = True
        phylactery.tags = [Tags.Construct, Tags.Dark]
        phylactery.resists[Tags.Dark] = 100

        if self.caster.source.summon(phylactery, Point(x, y)):
            self.caster.apply_buff(Soulbound(phylactery))
            if self.legacy:
                sorcery = TouchedBySorcery(self.legacy)
                sorcery.asset = sorcery.asset = ["MissingSynergies", "Statuses", "%s_eye" % self.legacy.name.lower()]
                phylactery.apply_buff(sorcery)

class RaiseDracolichSpell(Spell):

    def on_init(self):
        self.name = "Raise Dracolich"
        self.asset = ["MissingSynergies", "Icons", "raise_dracolich"]
        
        self.tags = [Tags.Dark, Tags.Dragon, Tags.Enchantment, Tags.Conjuration]
        self.level = 6
        self.max_charges = 2
        self.range = 8
        self.requires_los = 0

        self.upgrades["legacy"] = (1, 7, "Elemental Legacy", "The dracolich gains [100:damage] resistance of the same element as the breath weapon of dragon it was created from, and its breath weapon redeals half of its damage as that element.\nSkeletons raised by this breath, and the dracolich's soul jar, gain [100:damage] resistance to that element and a ranged attack of that element.")
        self.upgrades["dragon_mage"] = (1, 5, "Dragon Mage", "The dracolich can cast Touch of Death with a 3 turn cooldown.\nThis Touch of Death gains all of your upgrades and bonuses.")
        self.upgrades["forced"] = (1, 4, "Forced Conversion", "Can now target enemy dragons, dealing [100_dark:dark] damage instead of instantly killing. If this kills the target, raise it as a dracolich.")
    
    def get_description(self):
        return ("Kill target dragon minion and resurrect it as a dracolich with the same max HP, melee damage, breath damage, and breath range.\n"
                "The dracolich can create a soul jar that makes itself immortal as long as the jar exists, and its [dark] breath raises slain [living] enemies as friendly skeletons.\n"
                "Bonuses to [minion_health:minion_health] benefit the soul jar, and [minion_damage:minion_damage] benefit the skeletons.").format(**self.fmt_dict())
    
    def can_cast(self, x, y):
        if not Spell.can_cast(self, x, y):
            return False
        unit = self.caster.level.get_unit_at(x, y)
        if unit and Tags.Dragon in unit.tags:
            if not are_hostile(unit, self.caster):
                return True
            elif self.get_stat("forced"):
                return True
        return False

    def cast_instant(self, x, y):		
        unit = self.caster.level.get_unit_at(x, y)
        if unit and Tags.Dragon in unit.tags:
            self.caster.level.queue_spell(self.try_raise(unit))
            if not are_hostile(unit, self.caster):
                unit.cur_hp = 0
                unit.kill()
            elif self.get_stat("forced"):
                unit.deal_damage(self.get_stat("damage", base=100), Tags.Dark, self)
    
    def try_raise(self, unit):

        if unit and not unit.is_alive() and not self.caster.level.get_unit_at(unit.x, unit.y):

            unit.has_been_raised = True
            legacy = None
            dracolich = Dracolich()
            dracolich.max_hp = unit.max_hp

            for spell in unit.spells:
                if isinstance(spell, BreathWeapon):
                    if self.get_stat("legacy"):
                        legacy = spell.damage_type
                    breath = RaiseDracolichBreath(spell.damage, spell.range, legacy)
                    dracolich.spells[1] = breath
                elif spell.melee:
                    dracolich.spells[2].damage = spell.damage
            
            dracolich.spells[0] = RaiseDracolichSoulJar(legacy)

            if self.get_stat('dragon_mage'):
                touch = TouchOfDeath()
                touch.statholder = self.caster
                touch.max_charges = 0
                touch.cur_charges = 0
                touch.cool_down = 3
                dracolich.spells.insert(1, touch)
            
            self.summon(dracolich, target=unit)
            
            if legacy:
                dracolich.resists[legacy] += 100
        
        yield

class DragonFearBuff(Buff):

    def __init__(self, spell, element):
        self.spell = spell
        self.element = element
        Buff.__init__(self)

    def on_init(self):
        self.name = "Fear%s" % ((" (%s)" % self.element.name) if self.element else "")
        self.color = Tags.Dragon.color
        self.buff_type = BUFF_TYPE_CURSE
        self.stack_type = STACK_INTENSITY
        if self.element:
            self.resists[self.element] = -self.spell.get_stat("resistance_debuff")
        self.originally_coward = False
        self.owner_triggers[EventOnBuffRemove] = self.on_buff_remove
        self.asset = ["MissingSynergies", "Statuses", "dragon_fear"]
    
    def on_applied(self, owner):
        other_element = None
        for buff in self.owner.buffs:
            if isinstance(buff, DragonFearBuff) and buff is not self:
                if buff.element == self.element:
                    buff.turns_left = max(buff.turns_left, self.turns_left)
                    return ABORT_BUFF_APPLY
                else:
                    other_element = buff
        if other_element:
            self.originally_coward = other_element.originally_coward
            return
        if self.owner.is_coward and not self.owner.has_buff(CowardBuff):
            self.originally_coward = True
        self.owner.is_coward = True
    
    def on_unapplied(self):
        if not self.owner.has_buff(DragonFearBuff) and not self.originally_coward and not self.owner.has_buff(CowardBuff):
            self.owner.is_coward = False
    
    def on_buff_remove(self, evt):
        if isinstance(evt.buff, CowardBuff):
            self.owner.is_coward = True

class EyeOfTheTyrantBuff(Spells.ElementalEyeBuff):

    def __init__(self, spell, element):
        Spells.ElementalEyeBuff.__init__(self, element if element else Tags.Physical, 0, spell.get_stat("shot_cooldown"), spell)
        # To make sure the graphics display properly for a dragon with no breath weapon but don't debuff physical resist
        self.breath_element = element
        self.name = "Eye of the Tyrant"
        self.color = Tags.Dragon.color
        self.asset = ["MissingSynergies", "Statuses", "dragon_eye"]

    def on_shoot(self, target):
        unit = self.owner.level.get_unit_at(target.x, target.y)
        if unit:
            if self.spell.get_stat("paralyzing") and unit.has_buff(DragonFearBuff):
                unit.apply_buff(Stun(), self.spell.get_stat("fear_duration"))
            unit.apply_buff(DragonFearBuff(self.spell, self.breath_element), self.spell.get_stat("fear_duration"))

class EyeOfTheTyrantSpell(Spell):

    def on_init(self):
        self.range = 0
        self.max_charges = 4
        self.name = "Eye of the Tyrant"
        self.duration = 20
        self.shot_cooldown = 3

        self.fear_duration = 3
        self.resistance_debuff = 25

        self.upgrades["shot_cooldown"] = (-1, 3)
        self.upgrades["fear_duration"] = (3, 3)
        self.upgrades["paralyzing"] = (1, 2, "Paralyzing Fear", "[Feared:dragon] enemies that are gazed again will also be [stunned:stun] for the same duration.")
        self.upgrades["resistance_debuff"] = (25, 2)

        self.tags = [Tags.Dragon, Tags.Enchantment, Tags.Eye]
        self.level = 3

        self.asset = ["MissingSynergies", "Icons", "eye_of_the_tyrant"]

    def get_impacted_tiles(self, x, y):
        return [Point(unit.x, unit.y) for unit in list(self.caster.level.units) if not are_hostile(self.caster, unit) and Tags.Dragon in unit.tags]

    def cast_instant(self, x, y):
        dragons = [unit for unit in list(self.caster.level.units) if not are_hostile(self.caster, unit) and Tags.Dragon in unit.tags]
        for dragon in dragons:
            element = None
            for spell in dragon.spells:
                if isinstance(spell, BreathWeapon):
                    element = spell.damage_type
                    break
            dragon.apply_buff(EyeOfTheTyrantBuff(self, element), self.get_stat("duration"))

    def get_description(self):
        return ("For [{duration}_turns:duration], your [dragon] minions' gazes terrify enemies, causing them to run away from danger.\n"
                "Every [{shot_cooldown}_turns:shot_cooldown], inflict [fear:dragon] on a random enemy unit in line of sight for [{fear_duration}_turns:dragon].\n"
                "[Feared:dragon] enemies lose [{resistance_debuff}:damage] resistance of the dragon's breath weapon element for the duration.").format(**self.fmt_dict())

class DragonSwipe(Spell):

    def __init__(self, damage):
        Spell.__init__(self)
        self.damage = damage

    def on_init(self):
        self.name = "Swipe"
        self.description = "Hits in an arc"
        self.range = 1.5
        self.melee = True
        self.can_target_self = False
        self.damage_type = Tags.Physical

    def get_impacted_tiles(self, x, y):
        ball = self.caster.level.get_points_in_ball(x, y, 1, diag=True)
        aoe = [p for p in ball if 1 <= distance(p, self.caster, diag=True) < 2]
        return aoe

    def cast(self, x, y):
        damage = self.get_stat("damage")
        for p in self.get_impacted_tiles(x, y):
            unit = self.caster.level.get_unit_at(p.x, p.y)
            if unit and not are_hostile(self.caster, unit):
                continue
            self.caster.level.deal_damage(p.x, p.y, damage, self.damage_type, self)
            yield

class DraconianBrutality(Upgrade):

    def on_init(self):
        self.name = "Draconian Brutality"
        self.level = 5
        self.tags = [Tags.Dragon, Tags.Nature, Tags.Translocation]
        self.description = ("Each of your [dragon] minions has its basic melee attack replaced by a swipe attack that deals the same damage, but hits in an arc, and does not damage allies.\nIt also gains a dive attack that has the same melee damage, and the same range as its breath weapon.")
        self.global_triggers[EventOnUnitAdded] = self.on_unit_added
        self.asset = ["MissingSynergies", "Icons", "draconian_brutality"]
    
    def on_unit_added(self, evt):

        if are_hostile(self.owner, evt.unit) or Tags.Dragon not in evt.unit.tags:
            return
        
        melee_index = None
        melee_damage = None
        breath_range = None

        for i, spell in enumerate(evt.unit.spells):
            if isinstance(spell, SimpleMeleeAttack):
                melee_index = i
                melee_damage = spell.damage
            elif isinstance(spell, BreathWeapon):
                breath_range = spell.range
        
        if melee_damage is None:
            melee_damage = 8
        if breath_range is None:
            breath_range = 7

        swipe = DragonSwipe(melee_damage)
        swipe.caster = evt.unit
        swipe.owner = evt.unit
        if melee_index is not None:
            evt.unit.spells[melee_index] = swipe
        else:
            evt.unit.spells.append(swipe)
        
        dive = LeapAttack(melee_damage, breath_range)
        dive.name = "Dive"
        dive.caster = evt.unit
        dive.owner = evt.unit
        evt.unit.spells.append(dive)

class RazorScalesBuff(Thorns):
    def __init__(self):
        Thorns.__init__(self, 0)
        self.buff_type = BUFF_TYPE_PASSIVE
        self.resists[Tags.Physical] = 15
        self.name = "Razor Scales"
        self.color = Tags.Metallic.color
    def on_advance(self):
        self.damage = self.owner.resists[Tags.Physical]//3
        self.description = "Deals %d %s damage to melee attackers" % (self.damage, self.dtype.name)
    def on_applied(self, owner):
        self.on_advance()

class RazorScales(Upgrade):

    def on_init(self):
        self.name = "Razor Scales"
        self.level = 4
        self.tags = [Tags.Dragon, Tags.Metallic]
        self.description = ("Your [dragon] minions gain [15_physical:physical] resistance, and melee retaliation dealing [physical] damage equal to 1/3 of their [physical] resistance.")
        self.global_triggers[EventOnUnitAdded] = self.on_unit_added
        self.asset = ["MissingSynergies", "Icons", "razor_scales"]
    
    def on_unit_added(self, evt):
        if are_hostile(self.owner, evt.unit) or Tags.Dragon not in evt.unit.tags:
            return
        evt.unit.apply_buff(RazorScalesBuff())

class BreathOfAnnihilation(Upgrade):

    def on_init(self):
        self.name = "Breath of Annihilation"
        self.level = 7
        self.tags = [Tags.Dragon, Tags.Chaos]
        self.description = ("The breath weapons of your [dragon] minions deal damage in a 90 degree cone if previously narrower.\nWhen one of your [dragon] minions' breath weapon hits an enemy that is resistant to the breath weapon's element, redeal the resisted damage as a random element chosen from [fire], [lightning], [physical], [arcane], and [dark].")
        self.global_triggers[EventOnPreDamaged] = self.on_pre_damaged
        self.global_triggers[EventOnUnitAdded] = self.on_unit_added
        self.asset = ["MissingSynergies", "Icons", "breath_of_annihilation"]
        self.dtypes = [Tags.Fire, Tags.Lightning, Tags.Physical, Tags.Arcane, Tags.Dark]
    
    def on_pre_damaged(self, evt):
        if evt.damage <= 0 or not are_hostile(self.owner, evt.unit) or not isinstance(evt.source, BreathWeapon) or are_hostile(evt.source.owner, self.owner):
            return
        resisted_amount = math.floor(evt.damage*min(100, evt.unit.resists[evt.damage_type])/100)
        evt.unit.deal_damage(resisted_amount//2, random.choice(self.dtypes), self)
    
    def on_unit_added(self, evt):
        if are_hostile(evt.unit, self.owner) or Tags.Dragon not in evt.unit.tags:
            return
        for spell in evt.unit.spells:
            if not isinstance(spell, BreathWeapon):
                continue
            spell.angle = max(spell.angle, math.pi/4)

    # For my No More Scams mod
    def can_redeal(self, target, source, damage_type):
        if not isinstance(source, BreathWeapon):
            return False
        for dtype in self.dtypes:
            if not is_immune(target, self, dtype):
                return True
        return False

class TwistedRemainsBuff(Buff):
    def __init__(self, spell):
        self.spell = spell
        Buff.__init__(self)
    def on_init(self):
        self.buff_type = BUFF_TYPE_PASSIVE
        self.owner_triggers[EventOnDeath] = self.on_death
        self.description = "On death, splits into giant spiders, green slimes, and toxic worm balls based on max HP."
        self.color = Tags.Slime.color
    def on_death(self, evt):
        total = self.owner.max_hp
        while total > 0:
            unit_type = random.choice([GiantSpider, GreenSlime, WormBallToxic])
            unit = unit_type()
            total -= unit.max_hp
            apply_minion_bonuses(self.spell, unit)
            self.spell.summon(unit, target=self.owner, radius=5)

class ChaosAdaptationBuff(Buff):
    def on_init(self):
        self.buff_type = BUFF_TYPE_PASSIVE
        self.resists[Tags.Fire] = 50
        self.resists[Tags.Lightning] = 50
        self.resists[Tags.Physical] = 50
        self.owner_triggers[EventOnDamaged] = self.on_damaged
        self.description = "When damaged, adapts to that element."
        self.color = Tags.Chaos.color
    def on_damaged(self, evt):
        other_element = random.choice([tag for tag in self.owner.resists.keys() if self.owner.resists[tag] > 0])
        adapt_amount = random.randint(0, self.owner.resists[other_element])
        adapt_amount = min(adapt_amount, 100 - self.owner.resists[evt.damage_type])
        self.owner.resists[evt.damage_type] += adapt_amount
        self.owner.resists[other_element] -= adapt_amount

class TwistedMutationSpell(Spell):

    def on_init(self):
        self.name = "Twisted Mutation"
        self.asset = ["MissingSynergies", "Icons", "twisted_mutation"]
        self.level = 6
        self.tags = [Tags.Nature, Tags.Chaos, Tags.Enchantment, Tags.Conjuration]
        self.range = 8
        self.max_charges = 2
        self.minion_damage = 3

        self.upgrades["hp_bonus"] = (30, 2, "Twisted Vitality", "The target gains [30_HP:minion_health].")
        self.upgrades["on_death"] = (1, 4, "Twisted Remains", "On death, the target spawns giant spiders, green slimes, and large toxic worm balls based on its max HP.")
        self.upgrades["adapt"] = (1, 3, "Chaos Adaptation", "The target gains [50_physical:physical], [50_fire:fire], and [50_lightning:lightning] resistance.\nWhen it takes damage, its resistance to that damage type is increased by a random amount and resistance to another random damage type is decreased by the same amount, without increasing any resistance above 100 or decreasing below 0.")
    
    def get_description(self):
        return ("Can only target [living], [nature], or [demon] allies.\n"
                "The target becomes a [spider], [slime], and [poison] unit.\n"
                "It gains a passive web-weaving ability, [100_poison:poison] resistance, an aura that deals [2_poison:poison] damage to enemies in a [4_tile:radius] radius each turn, and a slime-like ability to randomly gain max HP and spawn mutant slime offshoots.\n"
                "The mutant slimes have the same max HP as the unit that spawned them, melee attacks that deal [{minion_damage}_poison:poison] damage, and all abilities granted by this spell.").format(**self.fmt_dict())
    
    def can_cast(self, x, y):
        if not Spell.can_cast(self, x, y):
            return False
        unit = self.caster.level.get_unit_at(x, y)
        if unit and not are_hostile(self.caster, unit) and (Tags.Living in unit.tags or Tags.Nature in unit.tags or Tags.Demon in unit.tags):
            return True
        return False
    
    def get_mutant_slime(self, max_hp):

        slime = GreenSlime()
        slime.name = "Mutant Slime"
        slime.asset = ["MissingSynergies", "Units", "mutant_slime"]

        slime.spells[0].damage = self.get_stat("minion_damage")
        slime.max_hp = max_hp
        slime.tags = [Tags.Slime, Tags.Spider, Tags.Poison]
        slime.source = self

        buff = None
        for b in slime.buffs:
            if isinstance(b, SlimeBuff):
                buff = b
        if buff:
            slime.buffs.remove(buff)
        buff = SlimeBuff(lambda: self.get_mutant_slime(max_hp))
        buff.buff_type = BUFF_TYPE_PASSIVE
        slime.buffs.append(buff)

        buff = SpiderBuff()
        buff.buff_type = BUFF_TYPE_PASSIVE
        slime.buffs.append(buff)

        buff = DamageAuraBuff(damage=2, damage_type=Tags.Poison, radius=4)
        buff.buff_type = BUFF_TYPE_PASSIVE
        slime.buffs.append(buff)

        if self.get_stat("on_death"):
            slime.buffs.append(TwistedRemainsBuff(self))
        
        if self.get_stat("adapt"):
            slime.buffs.append(ChaosAdaptationBuff())

        return slime
    
    def cast_instant(self, x, y):

        unit = self.caster.level.get_unit_at(x, y)
        if not unit:
            return

        if self.get_stat("hp_bonus"):
            unit.max_hp += self.get_stat("hp_bonus")
            unit.cur_hp += self.get_stat("hp_bonus")
        if Tags.Spider not in unit.tags:
            unit.tags.append(Tags.Spider)
            buff = SpiderBuff()
            buff.buff_type = BUFF_TYPE_PASSIVE
            unit.apply_buff(buff)
        
        if Tags.Slime not in unit.tags:
            unit.tags.append(Tags.Slime)
            buff = SlimeBuff(lambda: self.get_mutant_slime(unit.max_hp))
            buff.buff_type = BUFF_TYPE_PASSIVE
            unit.apply_buff(buff)
        
        if Tags.Poison not in unit.tags:
            unit.tags.append(Tags.Poison)
            unit.resists[Tags.Poison] += 100
            buff = DamageAuraBuff(damage=2, damage_type=Tags.Poison, radius=4)
            buff.buff_type = BUFF_TYPE_PASSIVE
            unit.apply_buff(buff)
        
        if self.get_stat("on_death"):
            unit.apply_buff(TwistedRemainsBuff(self))
        
        if self.get_stat("adapt"):
            unit.apply_buff(ChaosAdaptationBuff())

class CustomSpiritBuff(SpiritBuff):

    def __init__(self, spell, tag):
        self.spell = spell
        SpiritBuff.__init__(self, tag)

    def on_spell_cast(self, spell_cast_event):
        hp_gain = self.spell.get_stat("hp_gain")
        if (self.tag in spell_cast_event.spell.tags 
            and spell_cast_event.caster.is_player_controlled 
            and self.owner.level.can_see(self.owner.x, self.owner.y, spell_cast_event.x, spell_cast_event.y)):
            self.owner.max_hp += hp_gain
            self.owner.cur_hp += hp_gain
            self.owner.level.queue_spell(self.effect(spell_cast_event.x, spell_cast_event.y))

    def get_tooltip(self):
        return "Gain %d max HP whenever witnessing %s spell" % (self.spell.get_stat("hp_gain"), self.tag.name)

def get_spirit_combo(tags):
    if Tags.Fire in tags and Tags.Lightning in tags:
        return "Chaos"
    elif Tags.Fire in tags:
        if Tags.Arcane in tags:
            return "Starfire"
        else:
            return "Fire"
    elif Tags.Lightning in tags:
        if Tags.Ice in tags:
            return "Storm"
        else:
            return "Spark"

class CustomSpiritBlast(SimpleRangedAttack):

    def __init__(self, spell, tags):
        self.spell = spell
        SimpleRangedAttack.__init__(self, damage=spell.get_stat("minion_damage"), damage_type=tags if len(tags) == 2 else tags[0], range=spell.get_stat("minion_range"), radius=1)
        self.name = "%s Blast" % get_spirit_combo(tags)
    
    def get_description(self):
        if self.spell.get_stat("power"):
            if isinstance(self.damage_type, list):
                desc = "Deals %s and %s damage" % (self.damage_type[0].name, self.damage_type[1].name)
            else:
                desc = "Hits twice"
            return self.description + "\n%s" % desc
        else:
            return self.description
    
    def hit(self, x, y):
        if not self.spell.get_stat("power"):
            SimpleRangedAttack.hit(self, x, y)
        else:
            if isinstance(self.damage_type, list):
                for dtype in self.damage_type:
                    self.caster.level.deal_damage(x, y, self.get_stat("damage"), dtype, self)
            else:
                for _ in range(2):
                    self.caster.level.deal_damage(x, y, self.get_stat("damage"), self.damage_type, self)

class ElementalChaosSpell(Spell):

    def on_init(self):
        self.name = "Elemental Chaos"
        self.asset = ["MissingSynergies", "Icons", "elemental_chaos"]
        self.tags = [Tags.Arcane, Tags.Ice, Tags.Chaos, Tags.Conjuration]
        self.level = 5
        self.max_charges = 3
        self.range = 0

        self.minion_health = 36
        self.minion_damage = 11
        self.minion_range = 6
        self.hp_gain = 5
        self.thorns = 4

        self.upgrades["fire_focus"] = (1, 2, "Fire Focus", "The storm spirit is replaced by two fire spirits.", "focus")
        self.upgrades["lightning_focus"] = (1, 2, "Lightning Focus", "The starfire spirit is replaced by two spark spirits.", "focus")
        self.upgrades["hp_gain"] = (2, 3, "Max HP Gain", "Spirits gain [2:minion_health] more max HP when witnessing spells of their elements.")
        self.upgrades["thorns"] = (2, 2, "Melee Retaliation", "Spirits gain [2:minion_damage] more melee retaliation damage.")
        self.upgrades["power"] = (1, 6, "Elemental Power", "The attacks of hybrid spirits deal damage of both of their elements instead of randomly one of them.\nThe attacks of pure spirits hit twice.")
    
    def get_description(self):
        return ("Summon a starfire spirit, chaos spirit, and storm spirit near yourself.\n"
                "Each spirit has [{minion_health}_HP:minion_health], [{thorns}_damage:minion_damage] melee retaliation of their elements, and an attack with [{minion_range}_range:minion_range] and [1_radius:radius] that deals [{minion_damage}_damage:minion_damage] of a random one of their elements.\n"
                "Each spirit gains [{hp_gain}:minion_health] max HP when witnessing a spell of one of its elements.").format(**self.fmt_dict())
    
    def get_spirit(self, tags):
        spirit = Unit()
        combo = get_spirit_combo(tags)
        spirit.name = "%s Spirit" % combo
        spirit.asset_name = "%s_spirit" % combo.lower()
        spirit.max_hp = self.get_stat("minion_health")
        spirit.tags = tags
        for tag in tags:
            spirit.resists[tag] = 100
            spirit.buffs.append(CustomSpiritBuff(self, tag))
            spirit.buffs.append(Thorns(self.get_stat("thorns"), tag))
        spirit.spells = [CustomSpiritBlast(self, tags)]
        return spirit
    
    def cast_instant(self, x, y):
        spirits = [self.get_spirit([Tags.Fire, Tags.Lightning])]
        if self.get_stat("fire_focus"):
            spirits.extend([self.get_spirit([Tags.Fire]), self.get_spirit([Tags.Fire])])
        else:
            spirits.append(self.get_spirit([Tags.Lightning, Tags.Ice]))
        if self.get_stat("lightning_focus"):
            spirits.extend([self.get_spirit([Tags.Lightning]), self.get_spirit([Tags.Lightning])])
        else:
            spirits.append(self.get_spirit([Tags.Fire, Tags.Arcane]))
        for spirit in spirits:
            self.summon(spirit, radius=5, sort_dist=False)

class RuinBuff(Buff):
    def on_init(self):
        self.name = "Ruin"
        self.asset = ["MissingSynergies", "Statuses", "ruin"]
        self.color = Tags.Dark.color
        self.buff_type = BUFF_TYPE_CURSE
        self.description = "Cannot gain buffs.\nThis debuff cannot be removed prematurely."
    def on_applied(self, owner):
        self.owner.buff_immune = True
    def on_unapplied(self):
        if self.turns_left > 0:
            self.owner.apply_buff(RuinBuff(), self.turns_left)
        else:
            self.owner.buff_immune = False

class RuinAdept(Upgrade):
    def on_init(self):
        self.name = "Ruin Adept"
        self.level = 4
        self.description = "The duration of Ruin inflicted on enemies will be increased by this spell's bonuses to [duration:duration].\nThe duration of Ruin inflicted on allies will be decreased by this spell's bonuses to [duration:duration].\n"
        self.spell_bonuses[RuinousImpactSpell]["duration"] = 5
        self.spell_bonuses[RuinousImpactSpell]["adept"] = 1

class RuinousImpactSpell(Spell):

    def on_init(self):
        self.name = "Ruinous Impact"
        self.asset = ["MissingSynergies", "Icons", "ruinous_impact"]
        self.tags = [Tags.Dark, Tags.Chaos, Tags.Sorcery]
        self.level = 7
        self.max_charges = 1
        self.range = RANGE_GLOBAL
        self.requires_los = 0
        self.can_target_self = True

        self.damage = 80
        self.radius = 5
        self.duration = 33

        self.upgrades["damage"] = (20, 3)
        self.upgrades["radius"] = (2, 3, "Radius", "The length of the interval at which the damage and wall destruction chance decrease is increased by [2:radius].")
        self.add_upgrade(RuinAdept())

    def get_description(self):
        return ("Deal [fire], [lightning], [physical], and [dark] damage in a massive burst that covers the whole level, ignoring walls.\n"
                "The initial damage is [{damage}:damage] at the point of impact with a 100% chance to destroy walls.\n"
                "For every [{radius}_tiles:radius] away from the point of impact, the damage and chance to destroy walls is reduced by 5%.\n"
                "After dealing damage, remove all buffs from the target and inflict Ruin for a fixed [33_turns:duration], which prevents the target from gaining buffs and cannot be removed prematurely.\n"
                "The caster is not immune to this spell. Use with extreme caution.").format(**self.fmt_dict())
    
    def get_impacted_tiles(self, x, y):
        points = []
        stagenum = 0
        interval = self.get_stat('radius')
        for stage in Burst(self.caster.level, Point(x, y), interval*11, ignore_walls=True):
            if stagenum % interval == 0:
                points.extend(list(stage))
            stagenum += 1
        return points

    def hit(self, point, damage, duration_bonus):
        for dtype in [Tags.Fire, Tags.Lightning, Tags.Physical, Tags.Dark]:
            self.caster.level.deal_damage(point.x, point.y, damage, dtype, self)
        unit = self.caster.level.get_unit_at(point.x, point.y)
        if unit:
            buffs = list(unit.buffs)
            for buff in buffs:
                if buff.buff_type == BUFF_TYPE_BLESS:
                    unit.remove_buff(buff)
            duration = self.duration + duration_bonus*(1 if are_hostile(self.caster, unit) else -1)
            if duration > 0:
                unit.apply_buff(RuinBuff(), duration)

    def cast(self, x, y):
        damage = self.get_stat("damage")
        interval = self.get_stat('radius')
        duration_bonus = self.get_stat("duration", base=0) if self.get_stat("adept") else 0
        stagenum = 0
        step = 0
        for stage in Burst(self.caster.level, Point(x, y), interval*11, ignore_walls=True):
            for point in stage:
                self.hit(point, damage*(1 - 0.05*step), duration_bonus)
                if self.caster.level.tiles[point.x][point.y].is_wall() and random.random() < 1 - 0.05*step:
                    self.caster.level.make_floor(point.x, point.y)
            stagenum += 1
            if stagenum % interval == 0:
                step += 1
            yield

class CopperFurnaceSpell(Spell):

    def on_init(self):
        self.name = "Copper Furnace"
        self.asset = ["MissingSynergies", "Icons", "copper_furnace"]
        self.tags = [Tags.Metallic, Tags.Chaos, Tags.Conjuration]
        self.level = 7
        self.range = 5
        self.max_charges = 1
        self.must_target_walkable = True

        self.minion_health = 12
        self.minion_damage = 7
        self.minion_range = 8
        self.summon_chance = 10

        self.upgrades["summon_chance"] = (5, 3, "Summon Chance", "+5% summoning chance per turn for each of the Copper Furnace's summoning abilities.\nWhen you cast this spell while the Copper Furnace is already summoned, you will summon 1 additional random spider or mantis.")
        self.upgrades["tech_support"] = (1, 7, "Tech Support", "When you cast this spell while the Copper Furnace is already summoned, you will instead summon a copper fiend or furnace fiend, chosen at random.\nIf both the Copper Furnace and a fiend are already summoned, the spell will summon mantises and spiders on subsequent casts.")
        self.upgrades["max_charges"] = (3, 4)
    
    def fmt_dict(self):
        stats = Spell.fmt_dict(self)
        stats["furnace_hp"] = self.get_stat("minion_health")*10
        return stats
    
    def get_description(self):
        return ("Summon the Copper Furnace, which has [{furnace_hp}_HP:minion_health], an aura that deals [1_fire:fire] damage to enemies in a [8_tile:radius] radius, and a beam attack with [{minion_range}_range:minion_range] that deals [{minion_damage}_lightning:lightning] damage.\n"
                "Each turn, the Copper Furnace has a [{summon_chance}%_chance:conjuration] to summon a copper spider or copper mantis, and a [{summon_chance}%_chance:conjuration] to summon a furnace spider or furnace mantis.\n"
                "This spell is treated as if it has a base minion health stat of [12:minion_health]. The Copper Furnace benefits 10 times from bonuses to it.\n"
                "Casting this spell again while the Copper Furnace is already summoned will instead cause it to immediately trigger its passive summoning abilities.").format(**self.fmt_dict())
    
    def get_ally(self, is_copper, is_fiend=0):
        if is_copper:
            if is_fiend == 1:
                ally_type = CopperFiend
            elif is_fiend == 2:
                ally_type = CopperImp
            else:
                ally_type = random.choice([SpiderCopper, MetalMantisCopper])
        else:
            if is_fiend == 1:
                ally_type = FurnaceFiend
            elif is_fiend == 2:
                ally_type = FurnaceImp
            else:
                ally_type = random.choice([SpiderFurnace, MetalMantisFurnace])
        ally = ally_type()
        ally.source = self
        apply_minion_bonuses(self, ally)
        if is_fiend == 1:
            ally.spells[0] = SimpleSummon(lambda: self.get_ally(is_copper, is_fiend=2), num_summons=3, cool_down=7)
        return ally
    
    def can_cast(self, x, y):
        existing = None
        for unit in self.caster.level.units:
            if unit.name == "Copper Furnace":
                existing = unit
                break
        if existing:
            return x == self.caster.x and y == self.caster.y
        else:
            return Spell.can_cast(self, x, y) and not self.caster.level.get_unit_at(x, y)

    def cast_instant(self, x, y):

        existing = None
        existing_fiend = None
        for unit in self.caster.level.units:
            if unit.name == "Copper Furnace":
                existing = unit
                break
        for unit in self.caster.level.units:
            if unit.source is self and "Fiend" in unit.name:
                existing_fiend = unit
        if existing:
            if self.get_stat("tech_support") and not existing_fiend:
                self.summon(self.get_ally(random.choice([True, False]), is_fiend=1), target=existing)
            else:
                self.summon(self.get_ally(False), target=existing)
                self.summon(self.get_ally(True), target=existing)
                if self.get_stat("summon_chance") > 10:
                    self.summon(self.get_ally(random.choice([True, False])), target=existing)
            return
        
        unit = Unit()
        unit.unique = True
        unit.name = "Copper Furnace"
        unit.asset = ["MissingSynergies", "Units", "copper_furnace"]
        unit.max_hp = self.get_stat("minion_health")*10
        unit.tags = [Tags.Fire, Tags.Lightning, Tags.Metallic, Tags.Construct]
        unit.resists[Tags.Ice] = -100

        unit.spells.append(SimpleRangedAttack(damage=self.get_stat("minion_damage"), range=self.get_stat("minion_range"), beam=True, damage_type=Tags.Lightning))
        unit.buffs.append(DamageAuraBuff(damage=1, damage_type=Tags.Fire, radius=8))

        # Janky description change
        buff = GeneratorBuff(lambda: self.get_ally(False), self.get_stat("summon_chance")/100)
        buff.example_monster.name = "Furnace Spider or a Furnace Mantis"
        unit.buffs.append(buff)
        buff = GeneratorBuff(lambda: self.get_ally(True), self.get_stat("summon_chance")/100)
        buff.example_monster.name = "Copper Spider or a Copper Mantis"
        unit.buffs.append(buff)
        
        self.summon(unit, target=Point(x, y))

class MicrocosmBuff(Buff):

    def __init__(self, spell):
        self.spell = spell
        Buff.__init__(self)
    
    def on_init(self):
        self.global_triggers[EventOnDamaged] = self.on_damaged
        self.color = Tags.Chaos.color
        if self.spell.get_stat("volatile"):
            self.owner_triggers[EventOnDeath] = lambda evt: self.death_boom()
    
    def on_applied(self, owner):
        self.original_max_hp = self.owner.max_hp
        self.description = "When spell damage is dealt within %i tiles of this unit, lose 1 HP and randomly deal %i%% of that damage as fire, lightning, physical, or holy damage to all enemies in a %i tile burst from that tile. The damage cannot exceed %i." % (self.spell.get_stat("radius"), self.spell.get_stat("redeal_percentage"), self.spell.get_stat("blast_radius"), self.original_max_hp)
        if self.spell.get_stat("volatile"):
            self.description += "\nOn death, randomly deal %i fire, lightning, physical, or holy damage to all enemies in a %i radius." % (self.original_max_hp, self.spell.get_stat("radius"))
    
    def on_damaged(self, evt):
        if not isinstance(evt.source, Spell) or evt.source is self.spell:
            return
        if distance(evt.unit, self.owner) <= self.spell.get_stat("radius"):
            self.owner.level.queue_spell(self.boom(Point(evt.unit.x, evt.unit.y), min(evt.damage*self.spell.get_stat("redeal_percentage")//100, self.original_max_hp)))
    
    def boom(self, origin, damage):
        for stage in Burst(self.owner.level, origin, self.spell.get_stat("blast_radius")):
            for point in stage:
                self.hit(point.x, point.y, damage)
            yield
        if self.owner.cur_hp <= 1:
            self.owner.kill()
        else:
            self.owner.cur_hp -= 1

    def hit(self, x, y, damage):
        dtype = random.choice([Tags.Fire, Tags.Lightning, Tags.Physical, Tags.Holy])
        unit = self.owner.level.get_unit_at(x, y)
        if unit and not are_hostile(unit, self.owner):
            self.owner.level.show_effect(x, y, dtype)
        else:
            self.owner.level.deal_damage(x, y, damage, dtype, self.spell)
    
    def death_boom(self):
        for point in self.owner.level.get_points_in_ball(self.owner.x, self.owner.y, self.spell.get_stat("radius")):
            self.hit(point.x, point.y, self.original_max_hp)

class GenesisSpell(Spell):

    def on_init(self):
        self.name = "Genesis"
        self.asset = ["MissingSynergies", "Icons", "genesis"]
        self.level = 7
        self.tags = [Tags.Holy, Tags.Chaos, Tags.Conjuration, Tags.Sorcery]
        self.max_charges = 1

        self.requires_los = 0
        self.range = RANGE_GLOBAL

        self.minion_health = 20
        self.radius = 8
        self.blast_radius = 2
        self.redeal_percentage = 50

        self.upgrades["minion_health"] = (10, 3)
        self.upgrades["radius"] = (4, 3)
        self.upgrades["blast_radius"] = (1, 4, "Blast Radius", "The explosions caused by the Microcosm gain [1_radius:radius].")
        self.upgrades["volatile"] = (1, 3, "Volatile Cosmos", "When the Microcosm expires, it randomly deals [fire], [lightning], [physical], or [holy] damage equal to its original max HP to all enemies in its radius.\nCasting this spell again while you already have a Microcosm will now trigger this effect at the Microcosm's original location and teleport it to the target location.")
        self.upgrades["redeal_percentage"] = (25, 4, "Greater Genesis", "The explosions now deal damage equal to [75%:damage] of the triggering damage.")
    
    def get_existing(self):
        for unit in self.caster.level.units:
            if unit.name == "Microcosm":
                return unit
        return None

    def can_cast(self, x, y):
        if not Spell.can_cast(self, x, y):
            return False
        if self.caster.level.tiles[x][y].is_wall():
            return False
        existing = self.get_existing()
        unit = self.caster.level.get_unit_at(x, y)
        if unit:
            return unit is existing
        else:
            if existing:
                return bool(self.get_stat("volatile"))
            else:
                return True

    def get_impacted_tiles(self, x, y):
        existing = self.get_existing()
        if not existing:
            return list(self.caster.level.get_points_in_ball(x, y, self.get_stat("radius")))
        else:
            if not self.get_stat("volatile"):
                return [Point(x, y)]
            else:
                return list(self.caster.level.get_points_in_ball(x, y, self.get_stat("radius"))) + list(self.caster.level.get_points_in_ball(existing.x, existing.y, self.get_stat("radius")))

    def get_description(self):
        return ("Create a Microcosm, which has [{minion_health}_HP:minion_health], and [200%:damage] resistance to all damage and healing.\n"
                "Whenever spell damage is done within [{radius}_tiles:radius] of the Microcosm, an explosion occurs on that tile, randomly dealing [fire], [lightning], [physical], or [holy] damage to all enemies in a [{blast_radius}_tile:radius] burst. The damage is equal to [{redeal_percentage}%:damage] of the triggering damage but cannot exceed the Microcosm's original max HP. This is considered spell damage but cannot trigger itself. The Microcosm then loses [1_HP:damage].\n"
                "Casting this spell again while you already have a Microcosm will instead restore it to full HP.").format(**self.fmt_dict())
    
    def cast_instant(self, x, y):
        existing = self.get_existing()
        if existing:
            if self.get_stat("volatile"):
                buff = existing.get_buff(MicrocosmBuff)
                if buff:
                    buff.death_boom()
                if x != existing.x or y != existing.y:
                    if self.caster.level.can_move(existing, x, y, teleport=True):
                        self.caster.level.act_move(existing, x, y, teleport=True)
                        self.caster.level.show_effect(existing.x, existing.y, Tags.Translocation)
            existing.cur_hp = existing.max_hp
        else:
            unit = Unit()
            unit.unique = True
            unit.max_hp = self.get_stat("minion_health")
            unit.name = "Microcosm"
            unit.tags = [Tags.Holy, Tags.Chaos]
            unit.asset = ["MissingSynergies", "Units", "microcosm"]
            for tag in [Tags.Fire, Tags.Ice, Tags.Lightning, Tags.Poison, Tags.Holy, Tags.Dark, Tags.Arcane, Tags.Physical, Tags.Heal]:
                unit.resists[tag] = 200
            unit.buffs.append(MicrocosmBuff(self))
            unit.stationary = True
            unit.flying = True
            self.summon(unit, Point(x, y))

class OrbOfFleshBuff(Buff):

    def __init__(self, spell):
        self.spell = spell
        self.hp_threshold = spell.get_stat("minion_health")
        Buff.__init__(self)

    def on_init(self):
        self.color = Tags.Living.color
        self.name = "Enfleshed (%i HP)" % self.hp_threshold
        self.asset = ["MissingSynergies", "Statuses", "enfleshed"]
        self.nonliving = True
        self.owner_triggers[EventOnDamaged] = lambda evt: self.check_hp()
        self.owner_triggers[EventOnBuffApply] = self.on_buff_apply
        if self.spell.get_stat("explosion"):
            self.owner_triggers[EventOnDeath] = lambda evt: self.owner.level.queue_spell(self.boom())

    def on_applied(self, owner):
        self.owner.max_hp += self.hp_threshold
        self.owner.cur_hp += self.hp_threshold
        if Tags.Living not in self.owner.tags:
            self.owner.tags.append(Tags.Living)
        else:
            self.nonliving = False
        if are_hostile(self.owner, self.spell.caster):
            self.resists[Tags.Poison] = -100
            self.buff_type = BUFF_TYPE_CURSE
        else:
            self.resists[Tags.Heal] = -100

    def check_hp(self):
        if self.owner.cur_hp <= self.hp_threshold:
            self.owner.cur_hp = 0
            self.owner.kill()
    
    def on_advance(self):
        self.check_hp()
        if are_hostile(self.owner, self.spell.caster):
            self.owner.deal_damage(self.spell.get_stat("minion_damage"), Tags.Poison, self.spell)
        else:
            self.owner.deal_damage(-self.spell.get_stat("minion_damage"), Tags.Heal, self.spell)

    def on_unapplied(self):
        # Only remove living tag and added max HP after other on-death effects trigger
        self.owner.level.queue_spell(self.unmodify_unit())
    
    def unmodify_unit(self):
        self.owner.cur_hp -= self.hp_threshold
        self.owner.cur_hp = max(1 if self.owner.is_alive() else 0, self.owner.cur_hp)
        drain_max_hp(self.owner, self.hp_threshold)
        if self.nonliving and Tags.Living in self.owner.tags:
            self.owner.tags.remove(Tags.Living)
        yield
    
    def boom(self):
        for stage in Burst(self.owner.level, Point(self.owner.x, self.owner.y), math.ceil(self.spell.get_stat("minion_range")/2)):
            for point in stage:
                dtype = random.choice([Tags.Physical, Tags.Poison])
                unit = self.owner.level.get_unit_at(point.x, point.y)
                if unit and not are_hostile(self.spell.caster, unit):
                    self.owner.level.show_effect(point.x, point.y, dtype)
                else:
                    self.owner.level.deal_damage(point.x, point.y, self.owner.max_hp//5, dtype, self.spell)
            yield

    def on_buff_apply(self, evt):
        if not isinstance(evt.buff, ReincarnationBuff):
            return
        evt.buff.max_hp -= self.hp_threshold

class OrbOfFleshSpell(OrbSpell):

    def on_init(self):
        self.name = "Orb of Flesh"
        self.asset = ["MissingSynergies", "Icons", "orb_of_flesh"]
        self.tags = [Tags.Orb, Tags.Nature, Tags.Conjuration]
        self.level = 4
        self.max_charges = 4
        self.range = 9

        self.minion_health = 40
        self.minion_range = 3
        self.minion_damage = 3
        self.num_targets = 2

        self.upgrades["minion_range"] = (3, 2)
        self.upgrades["minion_damage"] = (2, 2)
        self.upgrades["num_targets"] = (2, 4, "Num Targets", "The orb can affect [2:num_targets] more targets.")
        self.upgrades["symbiosis"] = (1, 2, "Symbiosis", "Can also fuse with your other minions, healing them each turn instead of dealing damage, and decreasing [heal] resistance instead of [poison] resistance.")
        self.upgrades["explosion"] = (1, 4, "Gore Explosion", "On death, the affected unit explodes to randomly deal [poison] or [physical] damage equal to 20% of its max HP, to all enemies in a burst with radius equal to half of the orb's minion range, rounded up.")
    
    def get_description(self):
        return ("Summon a flesh orb with [{minion_health}_HP:minion_health] next to the caster. Each turn a piece of it detaches and fuses with a visible enemy up to [{minion_range}_tiles:minion_range] away, dying after [{num_targets}:num_targets] enemies are affected.\n"
                "Each target becomes [living], loses [100_poison:poison] resistance, and takes [{minion_damage}_poison:poison] damage per turn.\n"
                "Its max and current HP increases by amounts equal to the orb's max HP, but it will die instantly when its max HP drops to that amount or lower.\n"
                "The orb has no will of its own, each turn it will float one tile towards the target.\n"
                "The orb can be destroyed by poison damage.").format(**self.fmt_dict())

    def on_make_orb(self, orb):
        orb.resists[Tags.Poison] = 0
        orb.asset = ["MissingSynergies", "Units", "orb_of_flesh"]
        orb.targets_left = self.get_stat("num_targets")
    
    def on_orb_collide(self, orb, next_point):
        orb.level.show_effect(next_point.x, next_point.y, Tags.Tongue)
        yield

    def detach(self, orb, target):
        for point in orb.level.get_points_in_line(orb, target):
            orb.level.show_effect(point.x, point.y, Tags.Tongue)
            yield
        target.apply_buff(OrbOfFleshBuff(self))
        orb.targets_left -= 1
        if orb.targets_left <= 0:
            orb.kill()
            # In case the orb is resurrected
            orb.targets_left = self.get_stat("num_targets")

    def on_orb_move(self, orb, next_point):
        targets = orb.level.get_units_in_ball(next_point, self.get_stat("minion_range"))
        targets = [target for target in targets if orb.level.can_see(next_point.x, next_point.y, target.x, target.y) and not target.has_buff(OrbOfFleshBuff)]
        targets = [target for target in targets if target is not self.caster and target is not orb]
        if not self.get_stat("symbiosis"):
            targets = [target for target in targets if are_hostile(target, self.caster)]
        if not targets:
            return
        target = random.choice(targets)
        self.caster.level.queue_spell(self.detach(orb, target))

class ChaosEyeBuff(Spells.ElementalEyeBuff):
    def __init__(self, spell):
        Spells.ElementalEyeBuff.__init__(self, random.choice([Tags.Fire, Tags.Lightning, Tags.Physical]), spell.get_stat("damage"), spell.get_stat("shot_cooldown"), spell)
        self.name = "Eye of Chaos"
        self.color = Tags.Chaos.color
        self.asset = ["MissingSynergies", "Statuses", "chaos_eye"]
        freq_str = "each turn" if self.freq == 1 else ("every %d turns" % self.freq)
        self.description = "Deals %d fire, lightning, or physical damage to a random enemy in LOS %s" % (self.damage, freq_str)
        self.stack_type = STACK_INTENSITY
    def on_advance(self):
        Spells.ElementalEyeBuff.on_advance(self)
        self.element = random.choice([Tags.Fire, Tags.Lightning, Tags.Physical])

class EyesOfChaosSpell(Spell):

    def on_init(self):
        self.name = "Eyes of Chaos"
        self.asset = ["MissingSynergies", "Icons", "eyes_of_chaos"]
        self.tags = [Tags.Eye, Tags.Chaos, Tags.Enchantment]
        self.level = 6
        self.max_charges = 4
        self.range = 0

        self.damage = 15
        self.duration = 10
        self.shot_cooldown = 3

        self.upgrades['shot_cooldown'] = (-1, 3)
        self.upgrades['duration'] = (10, 3)
        self.upgrades['damage'] = (7, 4)
        self.upgrades['max_charges'] = (4, 5)

    def get_description(self):
        return ("Every [{shot_cooldown}_turns:shot_cooldown], deals [{damage}:damage] damage to a random enemy unit in line of sight.\n"
                "The damage type of this spell randomly changes between [fire], [lightning], and [physical] each turn.\n"
                "Multiple instances of this buff can stack.\n"
                "Lasts [{duration}_turns:duration].").format(**self.fmt_dict())
    
    def cast_instant(self, x, y):
        self.caster.apply_buff(ChaosEyeBuff(self), self.get_stat("duration"))

class AbyssalInsight(Upgrade):

    def on_init(self):
        self.name = "Abyssal Insight"
        self.asset = ["MissingSynergies", "Icons", "abyssal_insight"]
        self.level = 6
        self.radius = 2
        self.tags = [Tags.Dark, Tags.Eye]
        self.global_triggers[EventOnPreDamaged] = self.on_pre_damaged
    
    def get_description(self):
        return ("Your own [eye] spells redeal a quarter of their damage as [dark] damage.\n"
                "If you're [blind], your [eye] spells instead redeal half of their damage as [dark] damage. And whenever one of your [eye] spells hits an enemy, deal the same damage to enemies in a [{radius}_tile:radius] burst around that enemy along with half redealt as [dark] damage.").format(**self.fmt_dict())

    def qualifies(self, source):
        return isinstance(source, Spell) and source.caster is self.owner and Tags.Eye in source.tags

    def on_pre_damaged(self, evt):
        if evt.damage <= 0 or not self.qualifies(evt.source):
            return
        if self.owner.get_buff(BlindBuff):
            evt.unit.deal_damage(evt.damage//2, Tags.Dark, self)
            self.owner.level.queue_spell(self.boom(evt))
        else:
            evt.unit.deal_damage(evt.damage//4, Tags.Dark, self)
    
    def boom(self, evt):
        stagenum = 0
        for stage in Burst(self.owner.level, Point(evt.unit.x, evt.unit.y), self.get_stat("radius")):
            if stagenum != 0:
                for point in stage:
                    unit = self.owner.level.get_unit_at(point.x, point.y)
                    if unit:
                        if not are_hostile(unit, self.owner):
                            self.owner.level.show_effect(point.x, point.y, Tags.Dark)
                            self.owner.level.show_effect(point.x, point.y, evt.damage_type)
                        else:
                            unit.deal_damage(evt.damage//2, Tags.Dark, self)
                            unit.deal_damage(evt.damage, evt.damage_type, self)
                    else:
                        self.owner.level.show_effect(point.x, point.y, Tags.Dark)
                        self.owner.level.show_effect(point.x, point.y, evt.damage_type)
            stagenum += 1
            yield
    
    # For my No More Scams mod
    def can_redeal(self, target, source, damage_type):
        if not self.qualifies(source):
            return False
        return target.resists[Tags.Dark] < 100

class DivineGazeSpell(Spell):

    def on_init(self):
        self.name = "Divine Gaze"
        self.asset = ["MissingSynergies", "Icons", "divine_gaze"]
        self.level = 4
        self.tags = [Tags.Eye, Tags.Holy, Tags.Sorcery]
        self.range = RANGE_GLOBAL
        self.damage = 15
        self.max_charges = 8

        self.upgrades["damage"] = (7, 2)
        self.upgrades["max_charges"] = (10, 4)
        self.upgrades["order"] = (1, 4, "Eyes of Order", "Your non-stacking [eye] buffs are shot an additional time each.")
    
    def get_description(self):
        return ("Deal [{damage}_holy:holy] damage in a beam.\n"
                "When cast, each of your currently active [eye] buffs shoots its effect on all tiles in the same beam, each time reducing its duration by an amount equal to its [shot_cooldown:shot_cooldown]. If there isn't enough duration remaining, the effect will not occur.").format(**self.fmt_dict())
    
    def get_impacted_tiles(self, x, y):
        return list(Bolt(self.caster.level, self.caster, Point(x, y)))

    def eye_beam(self, target, eye):
        # None represents this spell's own beam
        if eye:
            if eye.turns_left < eye.freq:
                return
            eye.turns_left -= eye.freq
            if not eye.turns_left:
                self.caster.remove_buff(eye)
        damage = self.get_stat("damage")
        for point in Bolt(self.caster.level, self.caster, target):
            unit = self.caster.level.get_unit_at(point.x, point.y)
            self.caster.level.deal_damage(point.x, point.y, eye.damage if eye else damage, eye.element if eye else Tags.Holy, eye.spell if eye else self)
            if eye and unit:
                eye.on_shoot(point)
        yield

    def cast_instant(self, x, y):
        eyes = [None]
        eyes.extend([buff for buff in self.caster.buffs if isinstance(buff, Spells.ElementalEyeBuff)])
        for eye in eyes:
            for _ in range(1 + (self.get_stat("order") if eye and eye.stack_type != STACK_INTENSITY else 0)):
                self.caster.level.queue_spell(self.eye_beam(Point(x, y), eye))

def scam_summon_floating_eye_cast_instant(self, x, y):
    eye = FloatingEye()
    eye.spells = []
    eye.team = TEAM_PLAYER
    eye.max_hp += self.get_stat('minion_health')
    eye.turns_to_death = self.get_stat('minion_duration')

    p = self.caster.level.get_summon_point(x, y, flying=True)
    if p:
        # Ensure point exists before having the eye cast eye spells
        self.summon(eye, p)

        for spell in self.caster.spells:
            if Tags.Eye in spell.tags and spell.range == 0:
                # Temporarily change caster of spell
                spell = type(spell)()
                spell.caster = eye
                spell.owner = eye
                spell.statholder = self.caster
                self.caster.level.act_cast(eye, spell, eye.x, eye.y, pay_costs=False)

def new_summon_floating_eye_get_description(self):
    return ("Summon a floating eye.\n"
            "Floating eyes have [{minion_health}_HP:minion_health], [{shields}_SH:shields], float in place, and passively blink.\n"
            "Floating eyes have no attacks of their own, but will cast any self-targeted [eye] spells you know upon being summoned.\n"
            "Floating eyes vanish after [{minion_duration}_turns:minion_duration].").format(**self.fmt_dict())

SummonFloatingEye.get_description = new_summon_floating_eye_get_description

if "mods.BugsAndScams.NoMoreScams" not in sys.modules:
    SummonFloatingEye.cast_instant = scam_summon_floating_eye_cast_instant

class WarpLensStrike(LeapAttack):

    def __init__(self, spell):
        self.spell = spell
        LeapAttack.__init__(self, damage=spell.get_stat("minion_damage"), damage_type=Tags.Physical, range=RANGE_GLOBAL)
        self.name = "Warp-Lens Strike"

    def get_description(self):
        desc = "Melee or leap attack. Consumes duration from its summoner's eye buffs to add their effects to the attack."
        if self.spell.get_stat("cascade"):
            desc += " Cascades to a random target in LOS after killing the previous."
        return desc

    def can_redeal(self, target):
        for eye in [buff for buff in self.spell.caster.buffs if isinstance(buff, Spells.ElementalEyeBuff)]:
            if eye.turns_left >= eye.freq and not is_immune(target, eye.spell, eye.element):
                return True

    def hit(self, x, y, eyes, cascade=False):

        if distance(self.caster, Point(x, y), diag=True) > 1.5:
            leap_dest = self.get_leap_dest(x, y)
            path = self.caster.level.get_points_in_line(Point(self.caster.x, self.caster.y), Point(leap_dest.x, leap_dest.y), find_clear=not self.is_ghost)
            self.caster.invisible = True
            self.caster.level.act_move(self.caster, leap_dest.x, leap_dest.y, teleport=True)
            for point in path:
                self.caster.level.leap_effect(point.x, point.y, Tags.Translocation.color, self.caster)
                yield
            self.caster.invisible = False

        eyes_left = list(eyes)
        unit = self.caster.level.get_unit_at(x, y)
        if not unit:
            return
       
        for eye in eyes:
            if eye:
                if eye.turns_left < eye.freq:
                    eyes_left.remove(eye)
                    continue
                eye.turns_left -= eye.freq
                if not eye.turns_left:
                    self.spell.caster.remove_buff(eye)
                unit.deal_damage(eye.damage, eye.element, eye.spell)
                eye.on_shoot(unit)
            else:
                unit.deal_damage(self.get_stat("damage"), Tags.Physical, self)
            eyes_left.remove(eye)
            if not unit.is_alive():
                if not cascade or not eyes_left:
                    return
                targets = [unit for unit in self.caster.level.get_units_in_los(self.caster) if are_hostile(unit, self.caster) and self.can_cast(unit.x, unit.y)]
                if not targets:
                    return
                target = random.choice(targets)
                self.caster.level.queue_spell(self.hit(target.x, target.y, eyes_left, cascade=True))
                return
            yield
    
    def can_cast(self, x, y):
        if distance(self.caster, Point(x, y), diag=True) <= 1.5:
            return True
        return LeapAttack.can_cast(self, x, y)

    def cast(self, x, y):
        eyes = [None]
        eyes.extend([buff for buff in self.spell.caster.buffs if isinstance(buff, Spells.ElementalEyeBuff)])
        self.caster.level.queue_spell(self.hit(x, y, eyes, cascade=bool(self.spell.get_stat("cascade"))))
        yield

class LensArmorBuff(Buff):

    def __init__(self, spell):
        self.spell = spell
        Buff.__init__(self)
    
    def on_init(self):
        self.description = "Gains 1 SH whenever its summoner casts an eye spell."
        self.color = Tags.Shield.color
        self.global_triggers[EventOnSpellCast] = self.on_spell_cast
    
    def on_applied(self, owner):
        for buff in self.spell.caster.buffs:
            if isinstance(buff, Spells.ElementalEyeBuff):
                self.owner.add_shields(1)
    
    def on_spell_cast(self, evt):
        if evt.caster is self.spell.caster and Tags.Eye in evt.spell.tags:
            self.owner.add_shields(1)

class WarpLensGolemSpell(Spell):

    def on_init(self):
        self.name = "Warp-Lens Golem"
        self.asset = ["MissingSynergies", "Icons", "warp_lens_golem"]
        self.tags = [Tags.Arcane, Tags.Translocation, Tags.Eye, Tags.Conjuration]
        self.level = 5
        self.max_charges = 3
        self.must_target_empty = True
        self.must_target_walkable = True

        self.minion_health = 25
        self.minion_damage = 15

        self.upgrades["minion_damage"] = (7, 2)
        self.upgrades["armor"] = (1, 4, "Lens Armor", "The golem starts with 1 more [SH:shields] per [eye] buff you have at the time of casting, and gains [1_SH:shields] whenever you cast an [eye] spell.")
        self.upgrades["cascade"] = (1, 3, "Diffraction", "If the golem's current target dies before it finishes performing all of your eye on-hit effects, it will teleport to a new enemy in its line of sight to continue with the remaining effects.")
    
    def get_description(self):
        return ("Summon a Warp-Lens Golem with [{minion_health}_HP:minion_health] and [2_SH:shields].\n"
                "Each turn, it teleports next to a random enemy in its line of sight to perform a melee attack, dealing [{minion_damage}_physical:physical] damage plus the on-hit effects of all of your currently active [eye] buffs; each activation reduces the [eye] buff's duration by a number of turns equal to its [shot_cooldown:shot_cooldown].").format(**self.fmt_dict())
    
    def cast_instant(self, x, y):
        golem = Unit()
        golem.name = "Warp-Lens Golem"
        golem.asset = ["MissingSynergies", "Units", "warp_lens_golem"]
        golem.tags = [Tags.Arcane, Tags.Glass, Tags.Construct]
        golem.resists[Tags.Arcane] = 100
        golem.max_hp = self.get_stat("minion_health")
        golem.shields = 2
        golem.spells.append(WarpLensStrike(self))
        if self.get_stat("armor"):
            golem.buffs.append(LensArmorBuff(self))
        self.summon(golem, target=Point(x, y))

class MortalShackleBuff(Stun):
    def __init__(self, spell):
        self.spell = spell
        Stun.__init__(self)
    def on_init(self):
        self.name = "Mortal Shackle"
        self.asset = ["MissingSynergies", "Statuses", "mortal_shackle"]
        self.color = Tags.Metallic.color
        self.buff_type = BUFF_TYPE_CURSE
        weakness = self.spell.get_stat("resistance_reduction")
        self.resists[Tags.Physical] = -weakness
        self.resists[Tags.Poison] = -weakness
        self.owner_triggers[EventOnBuffApply] = self.on_buff_apply
    def on_buff_apply(self, evt):
        if isinstance(evt.buff, ReincarnationBuff):
            evt.unit.remove_buff(evt.buff)

class MortalChainmailBuff(StunImmune):
    def __init__(self, spell):
        self.spell = spell
        StunImmune.__init__(self)
    def on_init(self):
        self.name = "Mortal Chainmail"
        self.asset = ["MissingSynergies", "Statuses", "mortal_chainmail"]
        self.color = Tags.Metallic.color
        self.buff_type = BUFF_TYPE_BLESS
        weakness = self.spell.get_stat("resistance_reduction")
        self.resists[Tags.Physical] = weakness
        self.resists[Tags.Poison] = weakness
        self.owner_triggers[EventOnBuffApply] = self.on_buff_apply
    def on_buff_apply(self, evt):
        if isinstance(evt.buff, ReincarnationBuff):
            evt.unit.remove_buff(evt.buff)

class MortalCoilSpell(Spell):

    def on_init(self):
        self.name = "Mortal Coil"
        self.asset = ["MissingSynergies", "Icons", "mortal_coil"]
        self.tags = [Tags.Metallic, Tags.Nature, Tags.Sorcery, Tags.Enchantment]
        self.level = 3
        self.max_charges = 9
        self.range = 9
        self.requires_los = False
        self.can_target_empty = False

        self.damage = 15
        self.extra_damage = 2
        self.resistance_reduction = 25

        self.upgrades["extra_damage"] = (2, 2, "Extra Damage", "+2 extra damage per reincarnation lost.")
        self.upgrades["resistance_reduction"] = (25, 2)
        self.upgrades["delusion"] = (2, 3, "Mortal Delusion", "Every target will be affected as if it lost 2 additional reincarnations.\nThis does not allow the spell to chain to more targets, or trigger additional false deaths.")
        self.upgrades["friendly"] = (1, 4, "Life Binding", "Mortal Coil can now also affect your minions, instead healing them for an amount equal to this spell's damage plus extra damage per reincarnation lost, and granting them Chainmail, which increases [physical] and [poison] resistance and provides [stun] immunity for the duration.\nThe target still cannot gain reincarnations for the duration of Chainmail.")
    
    def can_cast(self, x, y):
        if not Spell.can_cast(self, x, y):
            return False
        unit = self.caster.level.get_unit_at(x, y)
        if not unit:
            return False
        if are_hostile(self.caster, unit):
            return True
        else:
            return self.get_stat("friendly")

    def get_description(self):
        return ("The target enemy loses all reincarnations, and is Shackled for a duration equal to the number of lives lost, during which it is [stunned], loses [{resistance_reduction}_physical:physical] and [{resistance_reduction}_poison:poison] resistance, and cannot gain reincarnations.\n"
                "The target then takes [{damage}_physical:physical] and [{damage}_poison:poison] damage. For each life lost, it takes an additional [{extra_damage}_physical:physical] and [{extra_damage}_poison:poison] damage, triggers all on-death effects, and the spell chains to a new target in range.\n"
                "This spell cannot remove lives from units that can gain clarity, or fake deaths if it fails to inflict Shackle.").format(**self.fmt_dict())
    
    def chain(self, start, end, already_hit, chains=1):

        for point in Bolt(self.caster.level, start, end, find_clear=False):
            self.caster.level.show_effect(point.x, point.y, Tags.Physical, minor=True)
            self.caster.level.show_effect(point.x, point.y, Tags.Poison, minor=True)
            yield
        
        unit = self.caster.level.get_unit_at(end.x, end.y)
        if not unit:
            return
        lives = 0
        if not unit.gets_clarity:
            respawn = unit.get_buff(ReincarnationBuff)
            if respawn:
                lives = respawn.lives
                unit.remove_buff(respawn)
        effective_lives = lives + self.get_stat("delusion")

        damage = self.get_stat("damage") + effective_lives*self.get_stat("extra_damage")
        if are_hostile(unit, self.caster):
            if effective_lives:
                unit.apply_buff(MortalShackleBuff(self), effective_lives)
            unit.deal_damage(damage, Tags.Physical, self)
            unit.deal_damage(damage, Tags.Poison, self)
        else:
            if effective_lives:
                unit.apply_buff(MortalChainmailBuff(self), effective_lives)
            unit.deal_damage(-damage, Tags.Heal, self)
        
        if unit.has_buff(MortalShackleBuff) or unit.has_buff(MortalChainmailBuff):
            for _ in range(lives):
                self.caster.level.event_manager.raise_event(EventOnDeath(unit, None), unit)
        
        if unit.is_alive():
            already_hit.append(unit)        
        chains = chains - 1 + lives
        if not chains:
            return
        targets = [target for target in self.caster.level.get_units_in_ball(end, self.get_stat("range")) if target not in already_hit and target is not self.caster]
        if not self.get_stat("friendly"):
            targets = [target for target in targets if are_hostile(target, self.caster)]
        if targets:
            self.caster.level.queue_spell(self.chain(end, random.choice(targets), already_hit, chains=chains))
    
    def cast(self, x, y):
        yield from self.chain(self.caster, Point(x, y), [])

BestowImmortality.get_description = lambda self: "Target unit gains the ability to reincarnate on death for [{duration}_turns:duration].".format(**self.fmt_dict())

class StandBackBuff(Buff):

    def __init__(self, spell):
        Buff.__init__(self)
        self.max_time = spell.get_stat("timer")
        self.cur_time = 0
        self.description = "Each turn, enemies within 4 tiles have a %i%% chance to be pushed 1 tile away." % math.floor(self.cur_time/self.max_time*100)
    
    def on_advance(self):
        self.cur_time += 1
        chance = self.cur_time/self.max_time
        self.description = "Each turn, enemies within 4 tiles have a %i%% chance to be pushed 1 tile away." % math.floor(chance*100)
        if random.random() < chance:
            self.owner.level.queue_spell(self.push())
    
    def push(self):
        targets = [target for target in self.owner.level.get_units_in_ball(self.owner, 4) if are_hostile(self.owner, target)]
        if not targets:
            return
        random.shuffle(targets)
        for target in targets:
            push(target, self.owner, 1)
            yield

class MorbidSphereHauntedBuff(Haunted):
    def __init__(self, spell):
        self.spell = spell
        Haunted.__init__(self)
    def on_advance(self):
        for _ in range(2):
            ghost = Ghost()
            self.spell.modify_unit(ghost, 4)
            ghost.turns_to_death = self.spell.get_stat("minion_duration", base=4)
            self.spell.summon(ghost, target=self.owner, radius=7, sort_dist=False)

class MorbidSphereHauntSpell(Spell):

    def __init__(self, spell):
        self.spell = spell
        self.duration = spell.get_stat("duration", base=7)
        Spell.__init__(self)
        self.name = "Haunt"
        self.description = "Haunts the target, spawning 2 ghosts nearby each turn for %d turns" % self.get_stat("duration")

    def can_cast(self, x, y):
        unit = self.caster.level.get_unit_at(x, y)
        if not unit:
            return False
        if unit:
            if unit.has_buff(MorbidSphereHauntedBuff):
                return False
        return Spell.can_cast(self, x, y)

    def cast_instant(self, x, y):
        unit = self.caster.level.get_unit_at(x, y)
        if unit:
            unit.apply_buff(MorbidSphereHauntedBuff(self.spell), self.get_stat("duration"))

class MorbidSphereSpell(OrbSpell):

    def on_init(self):
        self.name = "Morbid Sphere"
        self.asset = ["MissingSynergies", "Icons", "morbid_sphere"]
        self.tags = [Tags.Dark, Tags.Orb, Tags.Conjuration]
        self.level = 5
        self.range = 9
        self.max_charges = 4

        self.minion_health = 40
        self.minion_damage = 7
        self.timer = 20

        self.upgrades["timer"] = (-10, 4, "Morph Timer", "Summoned vampire bats take 10 fewer turns to transform.")
        self.upgrades["push"] = (1, 4, "Stand Back", "Each turn, a summoned vampire bat has a chance to push all enemy units within [4_tiles:radius] of itself [1_tile:radius] away.\nThe chance is equal to the number of turns it has been alive divided by the number of turns it takes to transform.")
        self.upgrades["higher"] = (1, 4, "Higher Vampires", "When a vampire bat is summoned, it has a 50% chance to instead be an armored vampire bat, vampiric mist, or vampire eye.")
        self.upgrades["ghost"] = (1, 2, "Bloody Mist", "Each turn, also summon a bloodghast, which inherits a quarter of the orb's bonus to max HP.")
        self.upgrades["orb_walk"] = (1, 4, "Night Lord", "Targeting an existing blood orb with another transforms it into a vampire necromancer or vampire count, chosen at random, which inherits the orb's full max HP bonus.")
    
    def get_description(self):
        return ("Summon an orb of vampiric blood next to the caster.\n"
                "Each turn the orb summons a vampire bat, which flees from enemies until it transforms into a vampire in [{timer}_turns:duration]. Vampire bats and vampires inherit half of the orb's bonus to max HP.\n"
                "The orb has no will of its own, each turn it will float one tile towards the target.\n"
                "The orb can be destroyed by holy damage.").format(**self.fmt_dict())

    def on_make_orb(self, orb):
        orb.resists[Tags.Holy] = 0
        orb.asset = ["MissingSynergies", "Units", "morbid_sphere"]

    def on_orb_collide(self, orb, next_point):
        orb.level.show_effect(next_point.x, next_point.y, Tags.Dark)
        yield
    
    bats = [VampireBat, ArmoredBat, VampireMist, VampireEye, CountBat, Necrobat]
    vampires = [Vampire, VampireArmored, GreaterVampire, MindVampire, VampireCount, VampireNecromancer]

    def modify_unit(self, unit, hp_div):
        original_max_hp = unit.max_hp
        apply_minion_bonuses(self, unit)
        unit.max_hp = original_max_hp + (self.get_stat("minion_health") - self.minion_health)//hp_div

    def get_unit(self, vamp_type, is_bat=True):

        unit = MorbidSphereSpell.bats[vamp_type]() if is_bat else MorbidSphereSpell.vampires[vamp_type]()
        self.modify_unit(unit, 2 if vamp_type < 4 else 1)
        
        if vamp_type == 5 and not is_bat:
            unit.spells[0].duration = self.get_stat("duration", base=unit.spells[0].duration)
            unit.spells[0].description = "Freezes the target for %i turns" % unit.spells[0].duration
            unit.spells[1] = MorbidSphereHauntSpell(self)
        
        morph_index = None
        morph = None
        for i, buff in enumerate(unit.buffs):
            if isinstance(buff, MatureInto if is_bat else RespawnAs):
                morph_index = i
                morph = buff
                break
        if morph:
            if is_bat:
                unit.buffs[morph_index] = MatureInto(lambda: self.get_unit(vamp_type, is_bat=False), self.get_stat("timer"))
            else:
                unit.buffs[morph_index] = RespawnAs(lambda: self.get_unit(vamp_type, is_bat=True))
        if is_bat and self.get_stat("push"):
            unit.buffs.append(StandBackBuff(self))

        return unit

    def on_orb_move(self, orb, next_point):
        vamp_type = 0
        if self.get_stat("higher") and random.random() < 0.5:
            vamp_type = random.choice([1, 2, 3])
        self.summon(self.get_unit(vamp_type), target=orb, radius=5)
        if self.get_stat("ghost"):
            ghost = Bloodghast()
            self.modify_unit(ghost, 4)
            self.summon(ghost, target=orb, radius=5)
    
    def on_orb_walk(self, existing):
        existing.kill(trigger_death_event=False)
        self.summon(self.get_unit(random.choice([4, 5]), is_bat=False), target=existing)
        yield

class GoldenTricksterShot(Spell):

    def __init__(self, spell):
        Spell.__init__(self)
        self.name = "Trick Shot"
        self.damage = spell.get_stat("minion_damage")
        self.range = spell.get_stat("minion_range")
        self.requires_los = 0 if spell.get_stat("phase") else 1
        self.bravado = spell.get_stat("bravado")
        self.description = "Pretends to deal damage. Hits 3 times. Randomly teleports the target up to 3 tiles away."

    def cast(self, x, y):
        for point in Bolt(self.caster.level, self.caster, Point(x, y), find_clear=self.requires_los):
            self.caster.level.show_effect(point.x, point.y, random.choice([Tags.Fire, Tags.Lightning, Tags.Physical]), minor=True)
            yield
        unit = self.caster.level.get_unit_at(x, y)
        if not unit:
            return
        damage = self.get_stat("damage")
        for _ in range(3):
            dtype = random.choice([Tags.Fire, Tags.Lightning, Tags.Physical])
            self.caster.level.event_manager.raise_event(EventOnPreDamaged(unit, damage, dtype, self), unit)
            self.caster.level.event_manager.raise_event(EventOnDamaged(unit, damage, dtype, self), unit)
        if self.bravado:
            for dtype in [Tags.Fire, Tags.Lightning, Tags.Physical]:
                self.caster.level.event_manager.raise_event(EventOnPreDamaged(unit, 30, dtype, self), unit)
        randomly_teleport(unit, 3)

class GoldenTricksterAura(Buff):

    def __init__(self, spell):
        self.spell = spell
        Buff.__init__(self)
    
    def on_init(self):
        self.radius = self.spell.get_stat("radius")
        self.shields = self.spell.get_stat("shields")
        self.description = "Each turn, pretends to take 1 dark damage from every enemy within %i tiles. Gains 1 SH when taking damage, up to %i." % (self.radius, self.shields)
        self.color = Tags.Shield.color
        self.owner_triggers[EventOnDamaged] = self.on_damaged
    
    def on_advance(self):
        enemies = [unit for unit in self.owner.level.get_units_in_ball(self.owner, self.radius) if are_hostile(self.owner, unit)]
        if not enemies:
            return
        for enemy in enemies:
            dummy_hit = SimpleMeleeAttack()
            dummy_hit.owner = enemy
            dummy_hit.caster = enemy
            self.owner.level.event_manager.raise_event(EventOnPreDamaged(self.owner, 1, Tags.Dark, dummy_hit), self.owner)
            self.owner.level.event_manager.raise_event(EventOnDamaged(self.owner, 1, Tags.Dark, dummy_hit), self.owner)

    def on_damaged(self, evt):
        if self.owner.shields < self.shields:
            self.owner.add_shields(1)

class GoldenTricksterSpell(Spell):
    
    def on_init(self):
        self.name = "Golden Trickster"
        self.asset = ["MissingSynergies", "Icons", "golden_trickster"]
        self.tags = [Tags.Holy, Tags.Arcane, Tags.Metallic, Tags.Chaos, Tags.Conjuration]
        self.level = 5
        self.max_charges = 3
        self.must_target_empty = True

        self.minion_health = 15
        self.minion_damage = 10
        self.minion_range = 10
        self.radius = 3
        self.shields = 1

        self.upgrades["radius"] = (2, 5)
        self.upgrades["shields"] = (5, 5)
        self.upgrades["phase"] = (1, 5, "Phase Shot", "The Golden Trickster's trick shot no longer requires line of sight.")
        self.upgrades["bravado"] = (1, 3, "Fool's Bravado", "The Golden Trickster's trick shot now pretends to deal an additional [30_fire:fire], [30_lightning:lightning], and [30_physical:physical] damage, but all of this extra damage behaves as if it is fully resisted by the target.")
        self.upgrades["mage"] = (1, 6, "Trickster Mage", "The Golden Trickster can cast Chaos Shuffle with a 3 turn cooldown.\nThis Chaos Shuffle gains all of your upgrades and bonuses.")
    
    def get_description(self):
        return ("Summon a Golden Trickster, a flying minion with many resistances, [{minion_health}_HP:minion_health], and [{shields}_SH:shields].\n"
                "It has a trick shot with [{minion_range}_range:minion_range], which hits 3 times. Each hit inflicts no actual damage but otherwise behaves as if [{minion_damage}_fire:fire], [{minion_damage}_lightning:lightning], or [{minion_damage}_physical:physical] damage have been done to the target. The target is also randomly teleported up to [3_tiles:range] away.\n"
                "Each turn, for each enemy within [{radius}_tiles:radius], it behaves as if it has taken [1_dark:dark] damage from that enemy. It gains [1_SH:shields] whenever it takes damage, up to a max of [{shields}_SH:shields].").format(**self.fmt_dict())

    def cast_instant(self, x, y):

        unit = Unit()
        unit.name = "Golden Trickster"
        unit.asset = ["MissingSynergies", "Units", "golden_trickster"]
        unit.tags = [Tags.Holy, Tags.Arcane, Tags.Metallic]
        unit.resists[Tags.Holy] = 100
        unit.resists[Tags.Arcane] = 100
        unit.stationary = True
        unit.flying = True
        unit.max_hp = self.get_stat("minion_health")
        unit.shields = self.get_stat("shields")
        unit.spells = [GoldenTricksterShot(self)]
        unit.buffs = [GoldenTricksterAura(self), TeleportyBuff(chance=.1, radius=8)]

        if self.get_stat('mage'):
            shuffle = ChaosShuffleSpell()
            shuffle.statholder = self.caster
            shuffle.max_charges = 0
            shuffle.cur_charges = 0
            shuffle.cool_down = 3
            shuffle.get_description = lambda: ""
            unit.spells.insert(0, shuffle)

        self.summon(unit, target=Point(x, y))

class RainbowEggBuff(Buff):

    def __init__(self, spell):
        self.spell = spell
        Buff.__init__(self)
    
    def on_init(self):
        self.absorbed = defaultdict(lambda : 0)
        self.global_triggers[EventOnDamaged] = self.on_damaged
        self.owner_triggers[EventOnDeath] = lambda evt: self.owner.level.queue_spell(self.hatch())
        self.weakness = Tags.Physical
        self.on_advance = self.change_element
        self.on_applied = lambda owner: self.change_element()

    def change_element(self):
        self.owner.resists[self.weakness] += 100
        self.weakness = random.choice([Tags.Fire, Tags.Ice, Tags.Lightning, Tags.Poison, Tags.Holy, Tags.Dark, Tags.Arcane, Tags.Physical])
        self.owner.resists[self.weakness] -= 100
    
    def on_damaged(self, evt):
        if distance(evt.unit, self.owner) > self.spell.get_stat("radius"):
            return
        self.absorbed[evt.damage_type] += evt.damage
    
    def hatch(self):
        drake = Unit()
        drake.name = "Rainbow Drake"
        drake.asset = ["MissingSynergies", "Units", "rainbow_drake"]
        drake.tags = [Tags.Living, Tags.Dragon]
        drake.flying = True
        drake.max_hp = self.spell.get_stat("minion_health")
        for key in self.absorbed.keys():
            drake.resists[key] = self.absorbed[key]
        breath = RainbowBreath(self.spell)
        drake.spells = [breath, SimpleMeleeAttack(self.spell.get_stat("minion_damage"))]
        drake.buffs = [RainbowDrakeBuff(breath)]
        if self.spell.get_stat("dragon_mage"):
            drake.buffs.append(RainbowDragonMage(self.spell))
        self.spell.summon(drake, target=self.owner)
        yield

class RainbowDrakeBuff(Buff):

    def __init__(self, breath):
        self.breath = breath
        Buff.__init__(self)
        self.description = "Each turn, breath weapon changes to a random element this unit resists."
        self.color = Tags.Dragon.color
        self.on_advance = self.change_element
        self.on_applied = lambda owner: self.change_element()
    
    def change_element(self):
        elements = []
        weights = []
        for element in list(self.owner.resists.keys()):
            if element == Tags.Heal:
                continue
            if self.owner.resists[element] <= 0:
                continue
            elements.append(element)
            weights.append(self.owner.resists[element])
        if elements:
            self.breath.damage_type = random.choices(elements, weights)[0]
        else:
            self.breath.damage_type = random.choice([Tags.Fire, Tags.Ice, Tags.Lightning, Tags.Poison, Tags.Holy, Tags.Dark, Tags.Arcane, Tags.Physical])

class RainbowBreath(BreathWeapon):

    def __init__(self, spell):
        BreathWeapon.__init__(self)
        self.name = "Rainbow Breath"
        self.damage_type = Tags.Physical # To be immediately changed
        self.damage = spell.get_stat("breath_damage")
        self.range = spell.get_stat("minion_range")
        self.penetration = spell.get_stat("penetration")
    
    def get_description(self):
        return "Deals damage in a cone. Penetrates %s resistance by an amount equal to half of the user's own %s resistance%s." % (self.damage_type.name, self.damage_type.name, (" plus %i" % self.penetration) if self.penetration else "")

    def per_square_effect(self, x, y):
        unit = self.caster.level.get_unit_at(x, y)
        if unit and are_hostile(self.caster, unit):
            amount = (self.caster.resists[self.damage_type]//2 if self.caster.resists[self.damage_type] >= 0 else 0) + self.penetration
            unit.resists[self.damage_type] -= amount
            unit.deal_damage(self.get_stat("damage"), self.damage_type, self)
            unit.resists[self.damage_type] += amount
        else:
            self.caster.level.deal_damage(x, y, self.get_stat("damage"), self.damage_type, self)
    
    def can_redeal(self, unit):
        return unit.resists[self.damage_type] - (self.caster.resists[self.damage_type]//2 if self.caster.resists[self.damage_type] >= 0 else 0) - self.penetration < 100

class RainbowDragonMage(Buff):

    def __init__(self, spell):
        self.spell = spell
        Buff.__init__(self)

    def on_init(self):
        self.owner_triggers[EventOnSpellCast] = self.on_spell_cast
        self.freq = 2 if self.spell.caster.has_buff(DragonArchmage) else 3
        self.color = Tags.Sorcery.color
        self.cooldown = self.freq
        self.update_description()
    
    def update_description(self):
        self.description = "Gains a random sorcery cantrip every %i turns, which can be only used once. Next one gained in %i turns." % (self.freq, self.cooldown)

    def on_applied(self, owner):
        self.cantrips = [type(spell) for spell in make_player_spells() if spell.level == 1 and Tags.Sorcery in spell.tags]
        self.add_cantrip()

    def add_cantrip(self):
        cantrip = random.choice(self.cantrips)()
        cantrip.caster = self.owner
        cantrip.owner = self.owner
        cantrip.max_charges = 0
        cantrip.cur_charges = 0
        cantrip.statholder = self.spell.caster
        self.owner.spells.insert(1, cantrip)

    def on_advance(self):
        self.cooldown -= 1
        if not self.cooldown:
            if not [spell for spell in self.owner.spells if type(spell) in self.cantrips]:
                self.add_cantrip()
                self.cooldown = self.freq
            else:
                self.cooldown = 1
        self.update_description()
    
    def on_spell_cast(self, evt):
        if type(evt.spell) in self.cantrips and evt.spell in self.owner.spells:
            self.owner.spells.remove(evt.spell)

class RainbowEggSpell(OrbSpell):

    def on_init(self):
        self.name = "Rainbow Egg"
        self.asset = ["MissingSynergies", "Icons", "rainbow_egg"]
        self.tags = [Tags.Dragon, Tags.Orb, Tags.Conjuration]
        self.level = 6
        self.max_charges = 2
        self.range = 9
        self.radius = 7

        self.minion_health = 45
        self.minion_damage = 8
        self.breath_damage = 11
        self.minion_range = 7
        self.penetration = 0

        self.upgrades["minion_health"] = (25, 3)
        self.upgrades["penetration"] = (25, 3, "Resistance Penetration", "The rainbow drake's breath weapon penetrates an additional 25 resistance.")
        self.upgrades["dragon_mage"] = (1, 3, "Dragon Mage", "The rainbow drake will gain a random [sorcery] cantrip every 3 turns if it does not have any, which can be used once before being removed.\nThese cantrips gain all of your upgrades and bonuses.")
    
    def get_description(self):
        return ("Summon a rainbow egg with [{minion_health}_HP:minion_health] next to the caster, which hatches into a rainbow drake with the same max HP and [{breath_damage}:minion_damage] breath damage upon death.\n"
                "The rainbow drake gains resistance to each element equal to half of all damage of that type done within [{radius}_tiles:radius] of the egg during its lifetime. Its breath weapon changes element randomly each turn to an element it resists, and penetrates enemy resistances by half of that amount.\n"
                "The egg has no will of its own, each turn it will float one tile towards the target.\n"
                "The egg's elemental weakness changes randomly each turn.").format(**self.fmt_dict())

    def on_make_orb(self, orb):
        orb.asset = ["MissingSynergies", "Units", "rainbow_egg"]
        orb.resists[Tags.Physical] = 0 # To be immediately changed
        orb.buffs.append(RainbowEggBuff(self))
    
    def on_orb_collide(self, orb, next_point):
        orb.level.show_effect(next_point.x, next_point.y, random.choice([Tags.Fire, Tags.Ice, Tags.Lightning, Tags.Poison, Tags.Holy, Tags.Dark, Tags.Arcane, Tags.Physical]))
        yield

class SpiritBombBuff(Buff):

    def __init__(self, spell, charges):
        Buff.__init__(self)
        self.spell = spell
        self.charges = charges
        self.base_damage = spell.get_stat("minion_damage")
        self.base_radius = spell.get_stat("radius")
        self.base_hp = spell.minion_health
        self.timer = 0
        self.warcry = spell.get_stat("warcry")
        self.duration = spell.get_stat("duration", base=3)
        self.on_applied = lambda owner: self.update_description()
        self.owner_triggers[EventOnDeath] = lambda evt: self.owner.level.queue_spell(self.boom())
        self.color = Tags.Holy.color
    
    def get_bonus(self):
        return self.charges//2 + self.timer//2 + (self.owner.max_hp - self.base_hp)//20
    
    def update_description(self):
        bonus = self.get_bonus()
        self.description = "On death, explodes to deal %i holy damage to all enemies in a %i tile burst and destroy all walls." % (self.base_damage + 10*bonus, self.base_radius + bonus)
        if self.warcry:
            self.description += "\nEach turn, the summoner of this unit has a 50%% chance of stunning or berserking a random enemy in line of sight for %i turns." % self.duration
    
    def on_advance(self):
        self.timer += 1
        self.update_description()
        if self.warcry and random.random() < 0.5:
            enemies = [unit for unit in self.owner.level.get_units_in_los(self.spell.caster) if are_hostile(self.spell.caster, unit)]
            if enemies:
                random.choice(enemies).apply_buff(random.choice([BerserkBuff, Stun])(), self.duration)
    
    def boom(self):
        bonus = self.get_bonus()
        damage = self.base_damage + 10*bonus
        radius = self.base_radius + bonus
        for stage in Burst(self.owner.level, Point(self.owner.x, self.owner.y), radius, ignore_walls=True):
            for point in stage:
                unit = self.owner.level.get_unit_at(point.x, point.y)
                if unit and are_hostile(unit, self.spell.caster):
                    unit.deal_damage(damage, Tags.Holy, self.spell)
                else:
                    self.owner.level.show_effect(point.x, point.y, Tags.Holy)
                    if self.owner.level.tiles[point.x][point.y].is_wall():
                        self.owner.level.make_floor(point.x, point.y)
            yield

class SpiritBombSpell(OrbSpell):

    def on_init(self):
        self.name = "Spirit Bomb"
        self.asset = ["MissingSynergies", "Icons", "spirit_bomb"]
        self.tags = [Tags.Holy, Tags.Orb, Tags.Conjuration]
        self.level = 7
        self.max_charges = 1
        self.range = 9

        self.minion_health = 40
        self.minion_damage = 50
        self.radius = 5

        self.upgrades["minion_damage"] = (30, 3)
        self.upgrades["radius"] = (3, 3)
        self.upgrades["warcry"] = (1, 2, "War Cry", "Each turn, the spirit bomb has a 50% chance of inflicting [stun] or [berserk] on a random enemy in your line of sight.")
    
    def get_description(self):
        return ("Summon an orb of extremely concentrated energy next to the caster, consuming all remaining charges of this spell.\n"
                "When the orb dies, it deals [{minion_damage}_holy:holy] damage to all enemies and destroys all walls in a [{radius}_tile:radius] burst, gaining +1 radius and +10 damage for every 2 turns it had existed, every 2 additional charge consumed, and each 20 bonus to max HP it had.\n"
                "The orb has no will of its own, each turn it will float one tile towards the target.\n"
                "The orb can be destroyed by dark damage.").format(**self.fmt_dict())
    
    def on_make_orb(self, orb):
        orb.asset = ["MissingSynergies", "Units", "spirit_bomb"]
        orb.resists[Tags.Dark] = 0
        orb.buffs.append(SpiritBombBuff(self, self.cur_charges))
        self.cur_charges = 0

    def on_orb_collide(self, orb, next_point):
        orb.level.show_effect(next_point.x, next_point.y, Tags.Holy)
        yield

class OrbOfMirrorsSpell(OrbSpell):

    def on_init(self):
        self.name = "Orb of Mirrors"
        self.asset = ["MissingSynergies", "Icons", "orb_of_mirrors"]
        self.tags = [Tags.Metallic, Tags.Eye, Tags.Orb, Tags.Conjuration]
        self.level = 5
        self.max_charges = 4
        self.range = 9

        self.minion_health = 8
        self.shields = 9

        self.reflect_chance = 50
        self.num_targets = 2

        self.upgrades["range"] = (5, 2)
        self.upgrades["reflect_chance"] = (25, 2)
        self.upgrades["num_targets"] = (1, 2)
    
    def get_description(self):
        return ("Summon a multifaceted orb of reflective metal next to the caster.\n"
                "Each turn, each [eye] buff belonging to each ally in the orb's line of sight has a [{reflect_chance}%:strikechance] chance to be reflected in the orb, applying its damage and effect to [{num_targets}:num_targets] random enemies in the orb's line of sight. Each target hit reduces the corresponding eye buff's duration by an amount equal to its [shot_cooldown:shot_cooldown].\n"
                "The orb has no will of its own, each turn it will float one tile towards the target.\n"
                "The orb can be destroyed by physical damage.").format(**self.fmt_dict())

    def on_make_orb(self, orb):
        orb.asset = ["MissingSynergies", "Units", "orb_of_mirrors"]
        orb.shields = self.shields
        orb.resists[Tags.Physical] = 0

    def on_orb_collide(self, orb, next_point):
        orb.level.show_effect(next_point.x, next_point.y, Tags.Physical)
        yield
    
    def reflect(self, origin):
        num_targets = self.get_stat("num_targets")
        units = [unit for unit in self.caster.level.get_units_in_los(origin) if not are_hostile(unit, self.caster) and unit.has_buff(Spells.ElementalEyeBuff)]
        random.shuffle(units)
        for unit in units:
            eyes = [buff for buff in unit.buffs if isinstance(buff, Spells.ElementalEyeBuff)]
            for eye in eyes:
                if random.random() >= self.get_stat("reflect_chance")/100 or eye.turns_left < eye.freq:
                    continue
                targets = [unit for unit in self.caster.level.get_units_in_los(origin) if are_hostile(self.caster, unit)]
                random.shuffle(targets)
                for target in targets[:num_targets]:
                    if eye.turns_left < eye.freq:
                        break
                    eye.turns_left -= eye.freq
                    if eye.turns_left <= 0:
                        eye.owner.remove_buff(eye)
                    self.caster.level.show_effect(0, 0, Tags.Sound_Effect, 'sorcery_ally')
                    for point in Bolt(self.caster.level, unit, origin):
                        self.caster.level.show_effect(point.x, point.y, eye.element, minor=True)
                        yield
                    for point in Bolt(self.caster.level, origin, target):
                        self.caster.level.show_effect(point.x, point.y, eye.element, minor=True)
                        yield
                    target.deal_damage(eye.damage, eye.element, eye.spell)
                    eye.on_shoot(target)
                    yield

    def on_orb_move(self, orb, next_point):
        self.caster.level.queue_spell(self.reflect(next_point))

class VolatileOrbSpell(OrbSpell):

    def on_init(self):
        self.name = "Volatile Orb"
        self.asset = ["MissingSynergies", "Icons", "volatile_orb"]
        self.tags = [Tags.Chaos, Tags.Orb, Tags.Conjuration, Tags.Sorcery]
        self.level = 2
        self.max_charges = 18
        self.range = 9

        self.minion_health = 40
        self.minion_damage = 6
        self.damage = 6
        self.radius = 6

        self.upgrades["minion_damage"] = (9, 2)
        self.upgrades["damage"] = (9, 2)
        self.upgrades["radius"] = (2, 2, "Radius", "Increases the upper limit of the orb's targeting radius.")
        self.upgrades["range"] = (5, 1)
        self.upgrades["max_charges"] = (8, 2)
    
    def fmt_dict(self):
        stats = Spell.fmt_dict(self)
        stats["total_damage"] = self.get_stat("damage") + self.get_stat("minion_damage")
        return stats

    def get_description(self):
        return ("Summon an orb of unstable energy next to the caster.\n"
                "Each turn, the orb targets a random number of enemies in a random radius between 1 to [{radius}:radius], dealing [fire], [lightning], or [physical] damage to each enemy equal to [{total_damage}:damage] divided by the number of enemies targeted, with a random damage modifier between -100% and +100%, rounded up. The total damage benefits from bonuses to both [spell_damage:sorcery] and [minion_damage:minion_damage].\n"
                "The orb has no will of its own, each turn it will float one tile towards the target.\n"
                "The orb has [{minion_health}_HP:minion_health], with 100% resistance to all damage but loses 10% each turn.").format(**self.fmt_dict())
    
    def on_orb_move(self, orb, next_point):

        for tag in orb.resists.keys():
            orb.resists[tag] -= 10

        radius = random.choice(list(range(1, self.get_stat("radius") + 1)))
        for point in self.caster.level.get_points_in_ball(next_point.x, next_point.y, radius):
            self.caster.level.show_effect(point.x, point.y, random.choice([Tags.Fire, Tags.Lightning, Tags.Physical]), minor=True)
        
        units = [unit for unit in self.caster.level.get_units_in_ball(next_point, radius) if are_hostile(unit, self.caster)]
        if not units:
            return
        random.shuffle(units)
        num_targets = random.choice(list(range(1, len(units) + 1)))
        damage = (self.get_stat("damage") + self.get_stat("minion_damage"))/num_targets
        for unit in units[:num_targets]:
            unit.deal_damage(math.ceil(damage*random.random()*2), random.choice([Tags.Fire, Tags.Lightning, Tags.Physical]), self)

    def on_make_orb(self, orb):
        orb.asset = ["MissingSynergies", "Units", "volatile_orb"]
    
    def on_orb_collide(self, orb, next_point):
        orb.level.show_effect(next_point.x, next_point.y, random.choice([Tags.Fire, Tags.Lightning, Tags.Physical]))
        yield

class OrbSubstitutionStack(Buff):

    def __init__(self, tag, amount):
        self.tag = tag
        Buff.__init__(self)
        self.resists[self.tag] = amount

    def on_init(self):
        self.name = "%s Protection" % self.tag.name
        self.stack_type = STACK_NONE
        self.color = self.tag.color

class OrbSubstitution(Upgrade):

    def on_init(self):
        self.name = "Orb Substitution"
        self.asset = ["MissingSynergies", "Icons", "orb_substitution"]
        self.level = 5
        self.tags = [Tags.Orb, Tags.Translocation]
        self.owner_triggers[EventOnPreDamaged] = self.on_pre_damaged
    
    def get_description(self):
        return ("Whenever you're about to take damage, if you have an active [orb] that can be harmed by that damage type and is on a walkable tile, swap places with that orb.\n"
                "You gain resistance to that damage type for [1_turn:duration] equal to [100:damage] minus the orb's resistance to that damage type, up to 100.\n"
                "You and the orb then both take that amount of damage.\n"
                "The duration of this damage resistance is fixed and does not benefit from bonuses.").format(**self.fmt_dict())

    def on_pre_damaged(self, evt):
        if evt.damage <= 0:
            return
        orbs = [unit for unit in self.owner.level.units if not are_hostile(self.owner, unit) and unit.has_buff(OrbBuff) and unit.resists[evt.damage_type] < 100]
        if not orbs:
            return
        orb = random.choice(orbs)
        if self.owner.level.tiles[orb.x][orb.y].can_walk:
            for p in self.owner.level.get_points_in_ball(orb.x, orb.y, 1):
                self.owner.level.show_effect(p.x, p.y, Tags.Translocation)
            for p in self.owner.level.get_points_in_ball(self.owner.x, self.owner.y, 1):
                self.owner.level.show_effect(p.x, p.y, Tags.Translocation)
            self.owner.level.act_move(self.owner, orb.x, orb.y, teleport=True, force_swap=True)
            amount = min(100, 100 - orb.resists[evt.damage_type])
            self.owner.apply_buff(OrbSubstitutionStack(evt.damage_type, amount), 1)
            orb.deal_damage(evt.damage, evt.damage_type, evt.source)

class LocusOfEnergy(Upgrade):

    def on_init(self):
        self.name = "Locus of Energy"
        self.asset = ["MissingSynergies", "Icons", "locus_of_energy"]
        self.tags = [Tags.Lightning, Tags.Arcane]
        self.level = 6
        self.damage = 12
        self.range = 10
    
    def get_description(self):
        return ("Each turn, shoot a number of beams each targeting a random enemy within [{range}_tiles:range].\n"
                "The number of beams is equal to the square root of 10% of the total duration of all of your buffs, rounded up.\n"
                "Each beam randomly deals [{damage}_lightning:lightning] or [{damage}_arcane:arcane] damage to all units in its path.\n").format(**self.fmt_dict())
    
    def on_advance(self):

        total_duration = 0
        for buff in self.owner.buffs:
            if buff.buff_type == BUFF_TYPE_BLESS:
                total_duration += buff.turns_left
        if not total_duration:
            return

        damage = self.get_stat("damage")
        beam_range = self.get_stat("range")
        for _ in range(math.ceil(math.sqrt(total_duration/10))):
            self.owner.level.queue_spell(self.beam(damage, beam_range))
    
    def beam(self, damage, beam_range):
        targets = [unit for unit in self.owner.level.get_units_in_ball(self.owner, beam_range) if are_hostile(self.owner, unit) and self.owner.level.can_see(self.owner.x, self.owner.y, unit.x, unit.y)]
        if not targets:
            return
        for point in Bolt(self.owner.level, self.owner, random.choice(targets)):
            self.owner.level.deal_damage(point.x, point.y, damage, random.choice([Tags.Lightning, Tags.Arcane]), self)
        yield

class AshenAvatarBuff(BlindBuff):

    def __init__(self, spell):
        self.spell = spell
        BlindBuff.__init__(self)
    
    def on_init(self):
        self.name = "Ashen Avatar"
        self.color = Tags.Fire.color
        self.asset = ["MissingSynergies", "Statuses", "ashen_avatar"]
        self.buff_type = BUFF_TYPE_BLESS
        self.small_mult = 0.1*self.spell.get_stat("mult")
        self.big_mult = 0.25*self.spell.get_stat("mult")
        self.minion_range = self.spell.get_stat("minion_range")
        self.minion_duration = self.spell.get_stat("minion_duration")
        resists = self.spell.get_stat("resists")
        for tag in [Tags.Fire, Tags.Dark, Tags.Poison]:
            self.resists[tag] = resists
        if self.spell.get_stat("power"):
            for tag in [Tags.Fire, Tags.Dark, Tags.Nature]:
                self.tag_bonuses[tag]["radius"] = 1
        self.global_triggers[EventOnDeath] = self.on_death
        self.global_triggers[EventOnDamaged] = self.on_damaged
    
    def on_damaged(self, evt):
        if evt.damage_type != Tags.Fire:
            return
        if not are_hostile(self.owner, evt.unit):
            return
        if not evt.unit.is_alive():
            return
        if evt.unit.has_buff(BlindBuff):
            evt.unit.apply_buff(Poison(), math.ceil(evt.damage*self.big_mult))
        else:
            evt.unit.apply_buff(BlindBuff(), math.ceil(evt.damage*self.small_mult))

    def on_death(self, evt):
        if Tags.Fire not in evt.unit.tags:
            return
        if evt.unit.source is self.spell:
            return
        phantom = GhostFire()
        phantom.name = "Ashen Phantom"
        phantom.asset = ["MissingSynergies", "Units", "ashen_phantom"]
        phantom.tags = [Tags.Fire, Tags.Dark, Tags.Nature, Tags.Undead]
        phantom.resists[Tags.Dark] = 100
        phantom.resists[Tags.Poison] = 100
        phantom.max_hp = evt.unit.max_hp
        phantom.spells[0] = SimpleRangedAttack(name="Ash Bolt", damage=math.ceil(phantom.max_hp*self.small_mult), damage_type=[Tags.Fire, Tags.Dark, Tags.Poison], range=self.minion_range, buff=BlindBuff, buff_duration=1)
        phantom.turns_to_death = self.minion_duration
        self.spell.summon(phantom, target=evt.unit, radius=5)

class AshenAvatarSpell(Spell):

    def on_init(self):
        self.name = "Ashen Avatar"
        self.asset = ["MissingSynergies", "Icons", "ashen_avatar"]
        self.tags = [Tags.Fire, Tags.Enchantment, Tags.Conjuration]
        self.level = 4
        self.max_charges = 4
        self.range = 0

        self.duration = 8
        self.minion_duration = 10
        self.minion_range = 5
        self.mult = 1
        self.resists = 75

        self.upgrades["duration"] = (8, 2)
        self.upgrades["resists"] = (25, 2)
        self.upgrades["mult"] = (1, 5, "Multipliers", "[Fire] damage now [blinds:blind] for a duration equal to [20%:duration] of the damage, and [poisons:poison] for a duration equal to [50%:duration] of the damage.\nAshen phantoms now deal damage equal to [20%:minion_damage] of their max HP.")
        self.upgrades["power"] = (1, 5, "Ashen Power", "[Fire], [dark], and [nature] spells and skills gain [1_radius:radius] for the duration.\nSpells and skills with more than one of these tags will benefit multiple times.")
    
    def fmt_dict(self):
        stats = Spell.fmt_dict(self)
        stats["small_mult"] = 10*self.get_stat("mult")
        stats["big_mult"] = 25*self.get_stat("mult")
        return stats

    def get_description(self):
        return ("[Blind] yourself for [{duration}_turns:duration], during which you gain [{resists}_fire:fire], [{resists}_dark:dark], and [{resists}_poison:poison] resistance, and the following benefits.\n"
                "All [fire] damage will [blind] enemies for a duration equal to [{small_mult}%:duration] of the damage. If the enemy is already [blind], instead inflict [poison] with a duration equal to [{big_mult}%:duration] of the damage.\n"
                "Whenever a [fire] unit other than an ashen phantom dies, summon an ashen phantom near it with the same max HP for [{minion_duration}_turns:minion_duration]; the phantom is a [fire] [dark] [nature] [undead]. Each phantom has an ash bolt with [{minion_range}_range:minion_range] that randomly deals [fire], [dark], or [poison] damage equal to [{small_mult}%:minion_damage] of its max HP and inflicts [1_turn:duration] of [blind].").format(**self.fmt_dict())
    
    def cast_instant(self, x, y):
        self.caster.apply_buff(AshenAvatarBuff(self), self.get_stat("duration"))

class DragonArchmage(Upgrade):

    def on_init(self):
        self.name = "Dragon Archmage"
        self.asset = ["MissingSynergies", "Icons", "dragon_archmage"]
        self.level = 6
        self.tags = [Tags.Dragon, Tags.Sorcery]
        self.description = "The spells that your [dragon] minions inherit from you have [-1_cooldown:cooldown], to a minimum of [2_turns:cooldown].\nWhenever one of your [dragon] minions casts a spell you know, you will also cast that spell for free at the same target if possible."
        self.global_triggers[EventOnUnitAdded] = self.on_unit_added
        self.global_triggers[EventOnSpellCast] = self.on_spell_cast

    def on_unit_added(self, evt):
        if Tags.Dragon not in evt.unit.tags or are_hostile(evt.unit, self.owner):
            return
        for spell in evt.unit.spells:
            # Assume only spells inherited from the player have levels
            if spell.level and spell.cool_down > 2:
                spell.cool_down -= 1
    
    def on_spell_cast(self, evt):
        if Tags.Dragon not in evt.caster.tags or are_hostile(evt.caster, self.owner):
            return
        for player_spell in self.owner.spells:
            if not isinstance(evt.spell, type(player_spell)):
                continue
            if player_spell.can_cast(evt.x, evt.y):
                self.owner.level.act_cast(self.owner, player_spell, evt.x, evt.y, pay_costs=False)

class CriticalInstabilityBuff(Buff):

    def __init__(self, spell):
        self.spell = spell
        Buff.__init__(self)

    def on_init(self):
        self.name = "Critical Instability"
        self.color = Tags.Chaos.color
        self.buff_type = BUFF_TYPE_CURSE
        self.owner_triggers[EventOnDeath] = self.on_death
        self.show_effect = False
    
    def on_death(self, evt):
        self.owner.level.queue_spell(self.spell.cast(self.owner.x, self.owner.y))

class AstralDecayBuff(Buff):
    def on_init(self):
        self.name = "Astral Decay"
        self.color = Tags.Arcane.color
        self.buff_type = BUFF_TYPE_CURSE
        self.resists[Tags.Arcane] = -100
        self.show_effect = False

class AstralMeltdownSpell(Spell):

    def on_init(self):
        self.name = "Astral Meltdown"
        self.asset = ["MissingSynergies", "Icons", "astral_meltdown"]
        self.tags = [Tags.Sorcery, Tags.Arcane, Tags.Chaos]
        self.level = 6
        self.max_charges = 2

        self.damage = 20
        self.radius = 2
        self.range = 10
        self.requires_los = 0

        self.upgrades["damage"] = (10, 4)
        self.upgrades["radius"] = (2, 6)
        self.upgrades["decay"] = (1, 5, "Astral Decay", "Inflict Astral Decay on targets for [1_turn:duration] before dealing damage; this duration is fixed and unaffected by bonuses.\nUnits with Astral Decay lose [100_arcane:arcane] resistance.")
        self.upgrades["vacuum"] = (1, 5, "Vacuum Burst", "Each explosion of this spell has a 20% chance to trigger another explosion on a random tile within the original explosion radius.")
    
    def get_description(self):
        return ("Inflict Critical Instability on targets in a [{radius}_tile:radius] burst, then deal [{damage}_arcane:arcane] damage, and randomly [{damage}_fire:fire], [{damage}_lightning:lightning], or [{damage}_physical:physical] damage. Melts walls on affected tiles.\n"
                "When a unit with Critical Instability dies, the explosion of this spell occurs again centered around its tile.\n"
                "Critical Instability is removed from all units at the beginning of your next turn.").format(**self.fmt_dict())

    def get_impacted_tiles(self, x, y):
            return [p for stage in Burst(self.caster.level, Point(x, y), self.get_stat('radius'), ignore_walls=True) for p in stage]
    
    def cast(self, x, y):
        self.caster.apply_buff(RemoveBuffOnPreAdvance(CriticalInstabilityBuff))
        damage = self.get_stat("damage")
        decay = self.get_stat("decay")
        if decay:
            self.caster.apply_buff(RemoveBuffOnPreAdvance(AstralDecayBuff))
        for stage in Burst(self.caster.level, Point(x, y), self.get_stat('radius'), ignore_walls=True):
            for p in stage:
                unit = self.caster.level.get_unit_at(p.x, p.y)
                if unit:
                    unit.apply_buff(CriticalInstabilityBuff(self))
                    if decay:
                        unit.apply_buff(AstralDecayBuff())
                if self.caster.level.tiles[p.x][p.y].is_wall():
                    self.caster.level.make_floor(p.x, p.y)
                self.caster.level.deal_damage(p.x, p.y, damage, Tags.Arcane, self)
                self.caster.level.deal_damage(p.x, p.y, damage, random.choice([Tags.Fire, Tags.Lightning, Tags.Physical]), self)
            yield
        if self.get_stat("vacuum") and random.random() < 0.2:
            point = random.choice(self.get_impacted_tiles(x, y))
            self.caster.level.queue_spell(self.cast(point.x, point.y))

class ChaosHailBuff(Buff):

    def __init__(self, spell):
        self.spell = spell
        Buff.__init__(self)
    
    def on_init(self):
        self.name = "Chaos Hail"
        self.color = Tags.Chaos.color
        self.damage = self.spell.get_stat("damage")
        self.radius = self.spell.get_stat("radius")
        self.num_targets = self.spell.get_stat("num_targets")
        self.max_hits = self.spell.get_stat("max_hits")
    
    def on_advance(self):
        targets = self.owner.level.get_units_in_ball(self.owner, self.radius)
        targets = [target for target in targets if are_hostile(self.owner, target) and self.owner.level.can_see(self.owner.x, self.owner.y, target.x, target.y)]
        self.owner.level.queue_spell(send_bolts(self.effect_path, self.effect_target, self.owner, targets[:self.num_targets]))
    
    def effect_path(self, point):
        self.owner.level.show_effect(point.x, point.y, random.choice([Tags.Ice, Tags.Fire, Tags.Lightning, Tags.Physical]), minor=True)
    
    def effect_target(self, point):
        for _ in range(random.choice(list(range(1, self.max_hits + 1)))):
            unit = self.owner.level.get_unit_at(point.x, point.y)
            if unit:
                unit.apply_buff(FrozenBuff(), 1)
            self.owner.level.deal_damage(point.x, point.y, self.damage, random.choice([Tags.Ice, Tags.Fire, Tags.Lightning, Tags.Physical]), self.spell)

class ChaosHailSpell(Spell):

    def on_init(self):
        self.name = "Chaos Hail"
        self.asset = ["MissingSynergies", "Icons", "chaos_hail"]
        self.tags = [Tags.Ice, Tags.Chaos, Tags.Enchantment]
        self.level = 5
        self.max_charges = 2
        self.range = 0

        self.duration = 5
        self.damage = 9
        self.radius = 6
        self.num_targets = 3
        self.max_hits = 3

        self.upgrades["duration"] = (5, 3)
        self.upgrades["radius"] = (3, 2)
        self.upgrades["num_targets"] = (2, 3)
        self.upgrades["max_hits"] = (2, 6, "Max Hits", "Each target can now be hit up to [5:num_targets] times.")
    
    def get_description(self):
        return ("Each turn, target up to [{num_targets}:num_targets] enemies in line of sight within [{radius}_tiles:radius] of the caster, and shoot 1 to [{max_hits}:num_targets] shards at each target.\n"
                "Each shard will [freeze] the target for [1_turn:duration], then deal [{damage}_ice:ice], [{damage}_fire:fire], [{damage}_lightning:lightning], or [{damage}_physical:physical] damage, chosen at random.\n"
                "Lasts [{duration}_turns:duration].").format(**self.fmt_dict())

    def cast_instant(self, x, y):
        self.owner.apply_buff(ChaosHailBuff(self), self.get_stat("duration"))

class UrticatingRainSpell(Spell):

    def on_init(self):
        self.name = "Urticating Rain"
        self.asset = ["MissingSynergies", "Icons", "urticating_rain"]
        self.tags = [Tags.Nature, Tags.Sorcery]
        self.level = 3
        self.max_charges = 18
        self.range = 0

        self.upgrades["max_charges"] = (8, 2)
        self.upgrades["poison"] = (1, 2, "Venomous Nettle", "Urticating Rain also inflicts [10_turns:duration] of [poison].")
        self.upgrades["blind"] = (1, 3, "Eye Irritant", "Urticating Rain also inflicts [1_turn:duration] of [blind].\nThis duration is fixed and unaffected by bonuses.")
        self.upgrades["fire"] = (1, 4, "Searing Pain", "Urticating Rain also deals [fire] damage.")
    
    def get_description(self):
        return ("Each of your [spider] allies, [thorn:nature] allies, and allies with [melee_retaliation:minion_damage] deals [3_physical:physical] damage to all enemies in a radius equal to its max HP divided by 10, rounded up.\n"
                "This damage is fixed, and cannot be increased using shrines, skills, or buffs.").format(**self.fmt_dict())

    def qualifies(self, u):
        return not are_hostile(u, self.caster) and (Tags.Spider in u.tags or "thorn" in u.name.lower() or u.has_buff(Thorns))

    def get_impacted_tiles(self, x, y):
        return [Point(u.x, u.y) for u in self.caster.level.units if self.qualifies(u)]
    
    def cast_instant(self, x, y):

        poison = self.get_stat("poison")
        poison_duration = self.get_stat("duration", base=10)
        blind = self.get_stat("blind")
        fire = self.get_stat("fire")

        for origin in [unit for unit in self.caster.level.units if self.qualifies(unit)]:

            effects_left = 7

            for unit in self.caster.level.get_units_in_ball(origin, math.ceil(origin.max_hp/10)):

                if not self.caster.level.are_hostile(self.caster, unit):
                    continue
                
                unit.deal_damage(3, Tags.Physical, self)
                if poison:
                    unit.apply_buff(Poison(), poison_duration)
                if blind:
                    unit.apply_buff(BlindBuff(), 1)
                if fire:
                    unit.deal_damage(3, Tags.Fire, self)
                effects_left -= 1

            # Show some graphical indication of this aura if it didnt hit much
            points = self.caster.level.get_points_in_ball(origin.x, origin.y, origin.max_hp//10)
            points = [p for p in points if not self.caster.level.get_unit_at(p.x, p.y)]
            random.shuffle(points)
            for _ in range(effects_left):
                if not points:
                    break
                p = points.pop()
                if fire:
                    damage_type = random.choice([Tags.Physical, Tags.Fire])
                else:
                    damage_type = Tags.Physical
                self.caster.level.show_effect(p.x, p.y, damage_type, minor=True)

class ChaosCatalystBuff(Buff):

    def __init__(self, spell):
        self.spell = spell
        Buff.__init__(self)
    
    def on_init(self):
        self.name = "Chaos Catalyst 1"
        self.color = Tags.Chaos.color
        self.stacks = 1
        self.owner_triggers[EventOnDeath] = self.on_death
    
    def on_death(self, evt):
        while self.stacks >= 10:
            self.stacks -= 10
            self.owner.level.queue_spell(self.spell.cast(self.owner.x, self.owner.y))
        if random.random() < self.stacks/10:
            self.owner.level.queue_spell(self.spell.cast(self.owner.x, self.owner.y))

    def update_name(self):
        self.name = "Chaos Catalyst %i" % self.stacks

class ChaosConcoctionSpell(Spell):

    def on_init(self):
        self.name = "Chaos Concoction"
        self.asset = ["MissingSynergies", "Icons", "chaos_concoction"]
        self.tags = [Tags.Chaos, Tags.Sorcery]
        self.level = 4
        self.max_charges = 8
        self.range = 8
        self.radius = 3
        self.damage = 7
        self.max_hits = 3

        self.upgrades["max_charges"] = (4, 2)
        self.upgrades["radius"] = (1, 3)
        self.upgrades["max_hits"] = (2, 4, "Max Hits", "Each target can now be hit up to [5:num_targets] times.")
        self.upgrades["cleanse"] = (1, 3, "Cleansing Acid", "Chaos Concoction no longer damages or acidifies allies.\nEach hit of Chaos Concoction will remove 1 debuff from an ally, and 1 buff from an enemy.")
        self.upgrades["catalyst"] = (1, 5, "Chaos Catalyst", "Each hit of Chaos Concoction applies a stack of Chaos Catalyst to [slime] allies.\nWhen a [slime] ally dies, it will consume all stacks of Chaos Catalyst to trigger the splash of Chaos Concoction once for every 10 stacks consumed. If there were less than 10 stacks remaining, there is a chance to trigger the splash equal to the number of stacks divided by 10.")
    
    def get_description(self):
        return ("Splash all units in a [{radius}_tile:radius] burst with caustic gel, hitting each unit 1 to [{max_hits}:num_targets] times.\n"
                "Each hit deals [{damage}_poison:poison], [{damage}_fire:fire], [{damage}_lightning:lightning], or [{damage}_physical:physical] damage, chosen at random, and has a 20% chance to inflict [acidify:poison], causing the target to lose [100_poison:poison] resistance.\n"
                "If the target is a [slime] ally, each hit will instead increase the target's current and max HP by an amount equal to its damage value, but the amount increased cannot exceed 20% of the target's max HP.").format(**self.fmt_dict())

    def hit(self, x, y, damage, cleanse=False, catalyst=False):
        tag = random.choice([Tags.Poison, Tags.Fire, Tags.Lightning, Tags.Physical])
        unit = self.caster.level.get_unit_at(x, y)
        if not unit:
            self.caster.level.show_effect(x, y, tag)
            return
        should_damage = True
        if not are_hostile(self.caster, unit):
            if Tags.Slime in unit.tags:
                amount = min(damage, unit.max_hp//5)
                unit.max_hp += amount
                unit.deal_damage(-amount, Tags.Heal, self)
                should_damage = False
                if catalyst:
                    existing = unit.get_buff(ChaosCatalystBuff)
                    if existing:
                        existing.stacks += 1
                        existing.update_name()
                    else:
                        unit.apply_buff(ChaosCatalystBuff(self))
            if cleanse:
                debuffs = [buff for buff in unit.buffs if buff.buff_type == BUFF_TYPE_CURSE]
                if debuffs:
                    unit.remove_buff(random.choice(debuffs))
                should_damage = False
        elif cleanse:
            buffs = [buff for buff in unit.buffs if buff.buff_type == BUFF_TYPE_BLESS]
            if buffs:
                unit.remove_buff(random.choice(buffs))
        if should_damage:
            if random.random() < 0.2:
                unit.apply_buff(Acidified())
            unit.deal_damage(damage, tag, self)
        else:
            self.caster.level.show_effect(x, y, tag)

    def cast(self, x, y):
        damage = self.get_stat("damage")
        max_hits = self.get_stat("max_hits")
        cleanse = self.get_stat("cleanse")
        catalyst = self.get_stat("catalyst")
        for stage in Burst(self.caster.level, Point(x, y), self.get_stat("radius")):
            for point in stage:
                for _ in range(random.choice(list(range(1, max_hits + 1)))):
                    self.hit(point.x, point.y, damage, cleanse, catalyst)
            yield

    def get_impacted_tiles(self, x, y):
        return [p for stage in Burst(self.caster.level, Point(x, y), self.get_stat('radius')) for p in stage]

class HighSorcerySpell(Spell):

    def on_init(self):
        self.name = "High Sorcery"
        self.asset = ["MissingSynergies", "Icons", "high_sorcery"]
        self.tags = [Tags.Fire, Tags.Lightning, Tags.Ice, Tags.Sorcery]
        self.level = 6
        self.max_charges = 15
        self.range = 5
        self.radius = 6
        self.damage = 13
        self.can_target_self = True
        self.requires_los = False

        self.upgrades["max_charges"] = (10, 3)
        self.upgrades["range"] = (5, 2)
        self.upgrades["radius"] = (3, 2)
        self.upgrades["anathema"] = (1, 4, "Anathema", "When dealing damage to an enemy, High Sorcery will always deal the damage type among [fire], [lightning], and [ice] that the enemy has the least resistance to.")

    def get_description(self):
        return ("If targeting yourself, randomly deal [{damage}_fire:fire], [{damage}_lightning:lightning], or [{damage}_ice:ice] damage in a [{radius}_tile:radius] burst.\n"
                "Otherwise, deal damage in a cone whose angle is 360 degrees divided by 1 plus twice the distance between you and the target tile, and whose height is this spell's radius plus that distance.\n"
                "For every tile between you and the target tile, this spell gains bonus damage percentage equal to 1 divided by the current number of tiles between you and the target tile. For example, targeting 3 tiles away will deal 1 + 1/2 + 1/3 times more damage.").format(**self.fmt_dict())

    def aoe(self, x, y):
        target = Point(x, y)
        dist = distance(self.caster, target)
        angle = math.pi/(1 + 2*dist)
        return Burst(self.caster.level, 
                    Point(self.caster.x, self.caster.y), 
                    self.get_stat('radius') + math.ceil(dist), 
                    burst_cone_params=BurstConeParams(target, angle))

    def get_impacted_tiles(self, x, y):
        return [p for stage in self.aoe(x, y) for p in stage]
    
    def hit(self, x, y, damage, anathema=False):
        tags = [Tags.Fire, Tags.Lightning, Tags.Ice]
        if not anathema:
            self.caster.level.deal_damage(x, y, damage, random.choice(tags), self)
            return
        unit = self.caster.level.get_unit_at(x, y)
        dtypes = tags
        if unit and are_hostile(unit, self.caster):
            min_resist = min([unit.resists[tag] for tag in tags])
            dtypes = [tag for tag in tags if unit.resists[tag] == min_resist]
        self.caster.level.deal_damage(x, y, damage, random.choice(dtypes), self)
    
    def cast(self, x, y):
        dist = distance(self.caster, Point(x, y))
        mult = 1
        anathema = self.get_stat("anathema")
        for i in range(1, math.ceil(dist) + 1):
            mult += 1/i
        damage = math.ceil(self.get_stat("damage")*mult)
        for stage in self.aoe(x, y):
            for point in stage:
                self.hit(point.x, point.y, damage, anathema)
            yield

class MassOfCursesBuff(Buff):

    def __init__(self, spell):
        self.spell = spell
        self.radius = spell.get_stat("radius")
        self.phase = spell.get_stat("phase")
        self.agony = spell.get_stat("agony")
        Buff.__init__(self)
    
    def on_init(self):
        self.global_triggers[EventOnSpellCast] = self.on_spell_cast
        self.color = Tags.Enchantment.color
        self.description = "When the wizard casts a single-target enchantment spell on this unit, cast a copy of that spell on each valid enemy target within %i tiles." % self.radius
    
    def on_spell_cast(self, evt):
        if not evt.caster.is_player_controlled or Tags.Enchantment not in evt.spell.tags:
            return
        if evt.spell.get_impacted_tiles(evt.x, evt.y) != [Point(self.owner.x, self.owner.y)]:
            return
        spell_copy = type(evt.spell)()
        spell_copy.max_charges = 0
        spell_copy.cur_charges = 0
        spell_copy.statholder = evt.caster
        spell_copy.owner = self.owner
        spell_copy.caster = self.owner
        if self.phase:
            spell_copy.requires_los = 0
            spell_copy.range = RANGE_GLOBAL if spell_copy.range >= 2 else spell_copy.range
        targets = [unit for unit in self.owner.level.get_units_in_ball(self.owner, self.radius) if are_hostile(unit, evt.caster) and spell_copy.can_cast(unit.x, unit.y)]
        duration = spell_copy.get_stat("duration")
        for target in targets:
            self.owner.level.act_cast(self.owner, spell_copy, target.x, target.y, pay_costs=False)
            if self.agony and duration:
                target.deal_damage(duration*2, Tags.Dark, self.spell)
        self.owner.cur_hp = 0
        self.owner.kill()

class MassOfCursesSpell(Spell):
    
    def on_init(self):
        self.name = "Mass of Curses"
        self.asset = ["MissingSynergies", "Icons", "mass_of_curses"]
        self.tags = [Tags.Dark, Tags.Enchantment, Tags.Conjuration]
        self.level = 5
        self.max_charges = 2
        self.radius = 2
        self.must_target_empty = True

        self.upgrades["range"] = (5, 2)
        self.upgrades["radius"] = (1, 4)
        self.upgrades["phase"] = (1, 3, "Phase Curses", "The mass of curses now ignores the copied spell's range and line of sight restrictions when copying it.")
        self.upgrades["agony"] = (1, 3, "Agonizing Curses", "The mass of curses now also deals [dark] damage to each affected enemy equal to twice the duration of the copied spell.")

    def get_description(self):
        return ("Summon a mass of curses, a stationary flying unit with fixed 1 HP, 200% resistance to all damage, and immunity to buffs and debuffs.\n"
                "When you cast a single-target [enchantment] spell targeting the mass of curses, the mass of curses is sacrificed to copy that spell onto every valid enemy target within [{radius}_tiles:radius] of itself.").format(**self.fmt_dict())

    def cast_instant(self, x, y):
        unit = Unit()
        unit.name = "Mass of Curses"
        unit.asset = ["MissingSynergies", "Units", "mass_of_curses"]
        unit.tags = [Tags.Undead, Tags.Enchantment]
        unit.max_hp = 1
        for tag in [Tags.Fire, Tags.Ice, Tags.Lightning, Tags.Poison, Tags.Holy, Tags.Dark, Tags.Arcane, Tags.Physical]:
            unit.resists[tag] = 200
        unit.buff_immune = True
        unit.debuff_immune = True
        unit.stationary = True
        unit.flying = True
        unit.buffs = [MassOfCursesBuff(self)]
        self.summon(unit, Point(x, y))

class SingularEye(Upgrade):

    def on_init(self):
        self.name = "Singular Eye"
        self.asset = ["MissingSynergies", "Icons", "singular_eye"]
        self.level = 4
        self.tags = [Tags.Eye]
        self.owner_triggers[EventOnBuffApply] = self.on_buff_apply
    
    def get_description(self):
        return ("When you gain an [eye] buff, if you have no other [eye] buffs, that [eye] buff gains [15_damage:damage] and [-1_shot_cooldown:shot_cooldown] (to a minimum of 1).\n"
                "This added damage affects even [eye] buffs that do not normally deal damage.").format(**self.fmt_dict())
    
    def on_buff_apply(self, evt):
        if not isinstance(evt.buff, Spells.ElementalEyeBuff):
            return
        for buff in self.owner.buffs:
            if isinstance(buff, Spells.ElementalEyeBuff) and buff is not evt.buff:
                return
        evt.buff.damage += 15
        evt.buff.freq = max(1, evt.buff.freq - 1)
        freq_str = "each turn" if evt.buff.freq == 1 else ("every %d turns" % evt.buff.freq)
        evt.buff.description = "Deals %d %s damage to a random enemy in LOS %s" % (evt.buff.damage, evt.buff.element.name, freq_str)

class CausticBurnBuff(Buff):

    def __init__(self, spell):
        self.spell = spell
        self.power = spell.get_stat("power")
        self.damage = spell.get_stat("damage", base=0) if spell.get_stat("bale") else 0
        Buff.__init__(self)
    
    def on_init(self):
        self.name = "Caustic Burn"
        self.asset = ["MissingSynergies", "Statuses", "caustic_burn"]
        self.color = Tags.Fire.color
        self.buff_type = BUFF_TYPE_CURSE
        self.stack_type = STACK_DURATION

    def on_advance(self):
        self.owner.deal_damage(self.turns_left + self.damage, Tags.Fire, self.spell)
        existing = self.owner.get_buff(Poison)
        if existing:
            existing.turns_left += self.power
        else:
            self.owner.apply_buff(Poison(), self.power)

class BrimstoneCurse(Buff):
    def __init__(self, amount):
        Buff.__init__(self)
        self.resists[Tags.Dark] = -amount
        self.color = Tags.Dark.color
        self.buff_type = BUFF_TYPE_CURSE
        self.update_name()
    def update_name(self):
        self.name = "Brimstone Curse %i" % -self.resists[Tags.Dark]

class BrimstoneClusterSpell(Spell):

    def on_init(self):
        self.name = "Brimstone Cluster"
        self.asset = ["MissingSynergies", "Icons", "brimstone_cluster"]
        self.tags = [Tags.Fire, Tags.Dark, Tags.Nature, Tags.Enchantment]
        self.level = 4
        self.max_charges = 6

        self.range = 8
        self.radius = 3
        self.power = 2
        self.num_targets = 4

        self.upgrades["max_charges"] = (6, 3)
        self.upgrades["radius"] = (1, 2)
        self.upgrades["num_targets"] = (2, 3, "More Clusters", "[2:num_targets] more explosions are created.")
        self.upgrades["power"] = (1, 4, "Power", "Brimstone Cluster inflicts [1:fire] more turn of Caustic Burn and reduces [dark] resistance by [1:dark] more per hit.\nEach turn of Caustic Burn increases the target's [poison] duration by [1:poison] more.")
        self.upgrades["bale"] = (1, 3, "Bale Burn", "The damage per turn of Caustic Burn is increased by this spell's bonuses to the [damage] stat from skills and buffs.")
    
    def get_description(self):
        return ("Create [{num_targets}:num_targets] explosions, each centered around a random point in a [{radius}_tile:radius] burst.\n"
                "Each explosion inflicts [{power}_turns:duration] of Caustic Burn on enemies in a [{radius}_tile:radius] burst, and permanently reduces their [dark] resistance by [{power}:dark].\n"
                "Caustic Burn stacks in duration. Each turn, it deals [fire] damage equal to its remaining duration, and inflicts [{power}_turns:duration] of [poison], stacking in duration with the target's existing [poison] if any.").format(**self.fmt_dict())

    def get_impacted_tiles(self, x, y):
        return [p for stage in Burst(self.caster.level, Point(x, y), self.get_stat('radius')) for p in stage]
    
    def cast(self, x, y):
        radius = self.get_stat("radius")
        power = self.get_stat("power")
        targets = self.get_impacted_tiles(x, y)
        for _ in range(self.get_stat("num_targets")):
            for stage in Burst(self.caster.level, random.choice(targets), radius):
                for point in stage:
                    self.hit(point.x, point.y, power)
            yield

    def hit(self, x, y, power):

        self.caster.level.show_effect(x, y, random.choice([Tags.Fire, Tags.Dark, Tags.Poison]))
        unit = self.caster.level.get_unit_at(x, y)
        if not unit or not are_hostile(unit, self.caster):
            return
        unit.apply_buff(CausticBurnBuff(self), power)

        existing = unit.get_buff(BrimstoneCurse)
        if not existing:
            unit.apply_buff(BrimstoneCurse(power))
        else:
            # A buff's resistance modifiers are only applied when the buff is initially applied,
            # so we have to manually set it on the target
            # At least make sure it unapplies correctly
            existing.resists[Tags.Dark] -= power
            unit.resists[Tags.Dark] -= power
            existing.update_name()

class ScapegoatBuff(Buff):
    def on_init(self):
        self.description = "Cannot move or act.\n\nAutomatically dies if there are no enemies in this level that are not scapegoats."
    def on_attempt_advance(self):
        return False
    def on_advance(self):
        if all(u.team == TEAM_PLAYER for u in self.owner.level.units if u.name != "Scapegoat"):
            self.owner.kill()

class CallScapegoatSpell(Spell):

    def on_init(self):
        self.name = "Call Scapegoat"
        self.asset = ["MissingSynergies", "Icons", "call_scapegoat"]
        self.tags = [Tags.Dark, Tags.Nature, Tags.Conjuration]
        self.level = 3
        self.max_charges = 6
        self.minion_health = 20
        self.num_summons = 4
        self.can_target_self = True

        self.upgrades["max_charges"] = (6, 2)
        self.upgrades["minion_health"] = (20, 3)
        self.upgrades["num_summons"] = (2, 3)
        self.upgrades["regen"] = (1, 2, "Unending Penance", "Scapegoats regenerate [10_HP:heal] per turn.")
        self.upgrades["death"] = (1, 3, "Grim Sacrifice", "If targeting yourself, this spell will now instead regain a charge and deal [dark] damage to each scapegoat equal to its current HP.")

    def get_description(self):
        return ("Summon [{num_summons}:num_summons] scapegoats.\n"
                "Scapegoats are [living], flying enemies with [{minion_health}_HP:minion_health], no resistances, and immunity to buffs (but not debuffs). They cannot move or act.\n"
                "Scapegoats die automatically if there are no other enemies in the level.").format(**self.fmt_dict())

    def cast_instant(self, x, y):

        if self.get_stat("death") and x == self.caster.x and y == self.caster.y:
            self.cur_charges = min(self.cur_charges + 1, self.get_stat("max_charges"))
            for unit in list(self.caster.level.units):
                if unit.name != "Scapegoat":
                    continue
                unit.deal_damage(unit.cur_hp, Tags.Dark, self)
            return
        
        health = self.get_stat("minion_health")
        regen = self.get_stat("regen")
        for _ in range(self.get_stat("num_summons")):
            unit = Unit()
            unit.name = "Scapegoat"
            unit.asset = ["MissingSynergies", "Units", "scapegoat"]
            unit.tags = [Tags.Living]
            unit.max_hp = health
            unit.flying = True
            unit.buff_immune = True
            if regen:
                unit.buffs.append(RegenBuff(10))
            unit.buffs.append(ScapegoatBuff())
            self.summon(unit, Point(x, y), radius=5, team=TEAM_ENEMY, sort_dist=False)

class FrigidFamineBuff(Buff):

    def __init__(self, spell):
        self.spell = spell
        self.ration = spell.get_stat("ration")
        self.wendigo = spell.get_stat("wendigo")
        self.starvation = spell.get_stat("starvation")
        self.counter = 0
        Buff.__init__(self)
    
    def on_init(self):
        self.name = "Frigid Famine"
        self.color = Tags.Ice.color
        self.global_triggers[EventOnPreDamaged] = self.on_pre_damaged

    def on_advance(self):
        for unit in list(self.owner.level.units):
            dtype = random.choice([Tags.Dark, Tags.Ice])
            starved = False
            if self.starvation and are_hostile(unit, self.owner) and unit.resists[Tags.Heal] > 0:
                unit.resists[dtype] -= unit.resists[Tags.Heal]
                starved = True
            dealt = unit.deal_damage(1, dtype, self.spell)
            if starved:
                unit.resists[dtype] += unit.resists[Tags.Heal]
            if dealt and self.wendigo:
                self.counter += 1
                if self.counter >= 100:
                    self.summon_wendigo()
                    self.counter -= 100
    
    def summon_wendigo(self):
        unit = Yeti()
        unit.name = "Wendigo"
        unit.asset = ["MissingSynergies", "Units", "wendigo"]
        apply_minion_bonuses(self.spell, unit)
        unit.spells[0].drain = True
        unit.spells[0].damage_type = Tags.Dark
        unit.buffs[0].damage_type = [Tags.Ice, Tags.Dark]
        unit.tags = [Tags.Ice, Tags.Dark, Tags.Undead]
        self.spell.summon(unit, target=self.owner, radius=RANGE_GLOBAL, sort_dist=False)

    def on_pre_damaged(self, evt):
        if evt.damage_type != Tags.Heal or evt.damage >= 0:
            return
        targets = list(self.owner.level.units)
        if self.ration:
            targets = [target for target in targets if are_hostile(self.owner, target)]
        if not targets:
            return
        random.shuffle(targets)
        num_targets = random.choice(range(1, len(targets) + 1))
        damage = -evt.damage//num_targets
        for target in targets[:num_targets]:
            dtype = random.choice([Tags.Dark, Tags.Ice])
            starved = False
            if self.starvation and are_hostile(target, self.owner) and target.resists[Tags.Heal] > 0:
                target.resists[dtype] -= target.resists[Tags.Heal]
                starved = True
            target.deal_damage(damage, dtype, self.spell)
            if starved:
                target.resists[dtype] += target.resists[Tags.Heal]

    def on_unapplied(self):
        if self.wendigo and random.random() < self.counter/100:
            self.summon_wendigo()

class FrigidFamineSpell(Spell):

    def on_init(self):
        self.name = "Frigid Famine"
        self.asset = ["MissingSynergies", "Icons", "frigid_famine"]
        self.tags = [Tags.Dark, Tags.Ice, Tags.Enchantment]
        self.level = 6
        self.max_charges = 2
        self.duration = 10
        self.range = 0

        self.upgrades["ration"] = (1, 3, "Rationing", "When a unit is healed, the resulting damage will now only target enemies.")
        self.upgrades["wendigo"] = (1, 5, "Summon Wendigo", "For every 100 damage dealt by this spell's per-turn effect, summon a wendigo at a random location.\nWendigos are [undead] minions with life-draining melee attacks and auras that deal [1_ice:ice] or [1_dark:dark] damage.\nWhen the effect expires, any accumulated damage will give a chance to summon a wendigo.")
        self.upgrades["starvation"] = (1, 4, "Starvation", "The damage dealt by this spell penetrates enemy resistances by an amount equal to each enemy's [heal] resistance.\n[Heal] resistance prevents healing but does not prevent attempted healing from being converted into damage by this spell; it is usually inflicted by the [poison] debuff.")
        self.upgrades["duration"] = (10, 2)

    def get_description(self):
        return ("Every turn, all units take [1_dark:dark] or [1_ice:ice] damage. This damage is fixed, and cannot be increased using shrines, skills, or buffs.\n"
                "Whenever a unit is about to be [healed:heal], before counting resistances, deal that amount as [dark] or [ice] damage divided among a random number of units.\n"
                "Lasts [{duration}_turns:duration].").format(**self.fmt_dict())

    def cast_instant(self, x, y):
        self.owner.apply_buff(FrigidFamineBuff(self), self.get_stat("duration"))

class NegentropySpell(Spell):

    def on_init(self):
        self.name = "Negentropy"
        self.asset = ["MissingSynergies", "Icons", "negentropy"]
        self.tags = [Tags.Fire, Tags.Ice, Tags.Sorcery]
        self.level = 3
        self.max_charges = 6

        self.radius = 4
        self.range = 8
        self.damage = 20
        self.duration = 3
        self.can_target_self = 0

        self.upgrades["radius"] = (2, 4)
        self.upgrades["range"] = (4, 2)
        self.upgrades["shock"] = (1, 5, "Thermal Shock", "[Frozen] enemies struck by the [fire] beam also take [physical] damage.")
        self.upgrades["thaw"] = (1, 4, "Violent Thawing", "[Frozen] enemies that take [fire] damage from the beam behave as if they have been unfrozen by [fire] damage [3:num_targets] additional times.")
        self.upgrades["can_target_self"] = (1, 4, "Heat Redistribution", "You can now target yourself with Negentropy.\nIf you do so, instead of shooting a beam, you will deal [fire] damage to enemies in this spell's radius.\nThis will not deal any extra damage based on the number of [frozen] enemies, or trigger the Violent Thawing upgrade.")

    def can_cast(self, x, y):
        if self.get_stat("can_target_self") and x == self.caster.x and y == self.caster.y:
            return True
        return Spell.can_cast(self, x, y)

    def get_description(self):
        return ("Absorb heat in a [{radius}_tile:radius] burst around yourself. Enemies in the affected area are [frozen] for [{duration}_turns:duration]. If an enemy is already [frozen], it instead takes [{damage}_ice:ice] damage.\n"
                "Then, release the gathered heat in a beam toward the target tile. Enemies in the path take [{damage}_fire:fire] damage, plus [3_fire:fire] damage for each enemy not immune to [freeze] that was in this spell's radius.").format(**self.fmt_dict())

    def cast(self, x, y):

        damage = self.get_stat("damage")
        duration = self.get_stat("duration")
        count = 0

        shock = self.get_stat("shock")
        thaw = self.get_stat("thaw")

        for stage in reversed(list(Burst(self.caster.level, Point(self.caster.x, self.caster.y), self.get_stat("radius")))):
            for point in stage:
                unit = self.caster.level.get_unit_at(point.x, point.y)
                if not unit or not are_hostile(unit, self.caster):
                    self.caster.level.show_effect(point.x, point.y, Tags.Ice)
                    continue
                if unit.has_buff(FrozenBuff):
                    unit.deal_damage(damage, Tags.Ice, self)
                else:
                    unit.apply_buff(FrozenBuff(), duration)
                if unit.resists[Tags.Ice] < 100:
                    count += 1
            yield

        if x == self.caster.x and y == self.caster.y:
            for stage in Burst(self.caster.level, Point(self.caster.x, self.caster.y), self.get_stat("radius")):
                for point in stage:
                    self.fire_hit(point, damage, count, shock, thaw, extra_damage=False)
                yield
        else:
            for point in Bolt(self.caster.level, self.caster, Point(x, y)):
                self.fire_hit(point, damage, count, shock, thaw)
            yield

    def fire_hit(self, target, damage, count, shock, thaw, extra_damage=True):

        unit = self.caster.level.get_unit_at(target.x, target.y)
        if not unit or not are_hostile(unit, self.caster):
            self.caster.level.show_effect(target.x, target.y, Tags.Fire)
            return
        
        frozen = unit.get_buff(FrozenBuff)
        if extra_damage:
            damage += 3*count
        damage_dealt = unit.deal_damage(damage, Tags.Fire, self)
        
        if frozen and damage_dealt and thaw and extra_damage and not unit.get_buff(FrozenBuff):
            for _ in range(3):
                self.caster.level.event_manager.raise_event(EventOnUnfrozen(unit, Tags.Fire), unit)
        
        if frozen and shock:
            unit.deal_damage(damage, Tags.Physical, self)

    def get_impacted_tiles(self, x, y):
        points = [p for stage in Burst(self.caster.level, self.caster, self.get_stat('radius')) for p in stage]
        points.extend(list(Bolt(self.caster.level, self.caster, Point(x, y))))
        return points

class StormBeam(Spell):

    def __init__(self, range):
        Spell.__init__(self)
        self.name = "Storm Beam"
        self.range = range
        self.damage_type = [Tags.Lightning, Tags.Ice]
        self.description = "Beam attack. Deals lightning and ice damage equal to 10% of the user's max HP."
    
    def cast_instant(self, x, y):
        for point in Bolt(self.caster.level, self.caster, Point(x, y)):
            self.caster.level.deal_damage(point.x, point.y, self.caster.max_hp//10, Tags.Lightning, self)
            self.caster.level.deal_damage(point.x, point.y, self.caster.max_hp//10, Tags.Ice, self)

class StormProtectionBuff(Buff):
    def on_init(self):
        self.name = "Storm Protection"
        self.asset = ["MissingSynergies", "Statuses", "storm_protection"]
        self.color = Tags.Lightning.color
        self.stack_type = STACK_REPLACE
    def on_applied(self, owner):
        self.resists[Tags.Lightning] = (100 - self.owner.resists[Tags.Lightning]) if self.owner.resists[Tags.Lightning] < 100 else 0
        self.resists[Tags.Ice] = (100 - self.owner.resists[Tags.Ice]) if self.owner.resists[Tags.Ice] < 100 else 0

class StormElementalBuff(Buff):

    def __init__(self, spell):
        self.spell = spell
        self.radius = spell.get_stat("radius")*2
        self.protection = spell.get_stat("protection")
        self.aggregate = spell.get_stat("aggregate")
        self.disperse = spell.get_stat("disperse")
        Buff.__init__(self)
    
    def on_init(self):
        self.name = "Storm Arc"
        self.color = Tags.Lightning.color
        self.description = "Each turn, storm energy arcs to each elemental ally in line of sight within %i tiles, dealing lightning and ice damage in a beam equal to 10%% of the ally's max HP." % self.radius
        self.global_triggers[EventOnDeath] = self.on_death
    
    def on_advance(self):
        units = [unit for unit in self.owner.level.get_units_in_ball(self.owner, self.radius) if Tags.Elemental in unit.tags and self.owner.level.can_see(unit.x, unit.y, self.owner.x, self.owner.y) and not are_hostile(unit, self.owner) and unit is not self]
        if not units:
            return
        random.shuffle(units)
        if self.protection:
            self.owner.apply_buff(RemoveBuffOnPreAdvance(StormProtectionBuff))
            for unit in units:
                unit.apply_buff(StormProtectionBuff())
        for unit in units:
            self.owner.level.queue_spell(self.beam(unit))

    def beam(self, unit):
        damage = unit.max_hp//10
        for point in list(Bolt(self.owner.level, self.owner, unit))[:-1]:
            self.owner.level.deal_damage(point.x, point.y, damage, Tags.Lightning, self)
            self.owner.level.deal_damage(point.x, point.y, damage, Tags.Ice, self)
        yield

    def on_death(self, evt):

        if evt.unit is self.owner and self.disperse:
            points = [point for point in self.owner.level.get_points_in_ball(self.owner.x, self.owner.y, self.spell.get_stat("radius")) if self.owner.level.can_see(self.owner.x, self.owner.y, point.x, point.y)]
            random.shuffle(points)
            for point in points:
                cloud_type = random.choice([StormCloud, BlizzardCloud])
                cloud = cloud_type(self.spell.caster)
                self.owner.level.add_obj(cloud, point.x, point.y)
            return
    
        if self.aggregate and Tags.Elemental in evt.unit.tags and evt.unit is not self and distance(evt.unit, self.owner) <= self.radius and self.owner.level.can_see(self.owner.x, self.owner.y, evt.unit.x, evt.unit.y):
            self.owner.max_hp += evt.unit.max_hp//5
            self.owner.cur_hp += evt.unit.max_hp//5

class GatheringStormSpell(Spell):

    def on_init(self):
        self.name = "Gathering Storm"
        self.asset = ["MissingSynergies", "Icons", "gathering_storm"]
        self.tags = [Tags.Lightning, Tags.Ice, Tags.Conjuration]
        self.level = 5
        self.max_charges = 4
        self.range = 8
        self.must_target_walkable = True

        self.radius = 4
        self.minion_range = 8

        self.upgrades["radius"] = (2, 4)
        self.upgrades["minion_range"] = (4, 2)
        self.upgrades["protection"] = (1, 3, "Storm Protection", "Each turn, [elemental] allies within the storm elemental's arcing distance gain [lightning] and [ice] resistances enough to put these resistances at 100.\nThis effect is removed at the start of the storm elemental's next turn.")
        self.upgrades["aggregate"] = (1, 5, "Elemental Aggregate", "When an [elemental] unit dies within the storm elemental's arcing distance, the storm elemental's max and current HP are increased by 20% of the dead elemental's HP.")
        self.upgrades["disperse"] = (1, 3, "Storm Dispersal", "When the storm elemental dies, it creates thunderstorm and blizzard clouds in an area around itself with radius equal to this spell's radius.")

    def can_cast(self, x, y):
        if not Spell.can_cast(self, x, y):
            return False
        unit = self.caster.level.get_unit_at(x, y)
        if unit:
            return unit.name == "Storm Elemental"
        return True

    def fmt_dict(self):
        stats = Spell.fmt_dict(self)
        stats["double_radius"] = self.get_stat("radius")*2
        return stats

    def get_description(self):
        return ("Consume all thunderstorm and blizzard clouds within [{radius}_tiles:radius] of the target tile to summon an immobile storm elemental with max HP and duration based on the damage, strikechance, and duration of clouds consumed, or teleport an existing storm elemental and boost its HP and duration.\n"
                "The storm elemental has a beam attack with [{minion_range}_range:minion_range] that deals [lightning] and [ice] damage equal to 10% of its max HP. Each turn, storm energy arcs from the storm elemental to each [elemental] ally in LOS within [{double_radius}_tiles:radius], dealing [lightning] and [ice] damage equal to 10% of the ally's max HP to units in between.").format(**self.fmt_dict())

    def cast(self, x, y):

        existing = None
        for unit in self.caster.level.units:
            if unit.name == "Storm Elemental":
                existing = unit
                break

        if existing and (existing.x != x or existing.y != y) and self.caster.level.can_move(existing, x, y, teleport=True):
            self.caster.level.show_effect(existing.x, existing.y, Tags.Translocation)
            self.caster.level.act_move(existing, x, y, teleport=True)

        cloud_damage = 0
        cloud_duration = 0

        def bolt(source):

            tag = None
            nonlocal cloud_damage
            nonlocal cloud_duration

            cloud = self.caster.level.tiles[source.x][source.y].cloud
            if isinstance(cloud, StormCloud):
                tag = Tags.Lightning
                cloud_damage += cloud.damage*cloud.strikechance
            elif isinstance(cloud, BlizzardCloud):
                tag = Tags.Ice
                cloud_damage += cloud.damage
            else:
                return
            cloud_duration += cloud.duration
            cloud.kill()
            
            for point in Bolt(self.caster.level, source, Point(x, y)):
                self.caster.level.show_effect(point.x, point.y, tag, minor=True)
                yield True
            yield False

        points = [point for point in self.caster.level.get_points_in_ball(x, y, self.get_stat("radius")) if self.caster.level.can_see(point.x, point.y, x, y) and type(self.caster.level.tiles[point.x][point.y].cloud) in [StormCloud, BlizzardCloud]]
        if not points:
            return
        bolts = [bolt(source) for source in points]
        while bolts:
            bolts = [bolt for bolt in bolts if next(bolt)]
            yield

        if existing:
            health = math.floor(cloud_damage*0.2)
            existing.max_hp += health
            existing.deal_damage(-health, Tags.Heal, self)
            existing.turns_to_death += math.floor(cloud_duration*0.1)
            return

        unit = Unit()
        unit.name = "Storm Elemental"
        unit.asset = ["MissingSynergies", "Units", "storm_elemental"]
        unit.unique = True
        unit.tags = [Tags.Lightning, Tags.Ice, Tags.Elemental]
        unit.resists[Tags.Lightning] = 100
        unit.resists[Tags.Ice] = 100
        unit.resists[Tags.Physical] = 50
        unit.stationary = True
        unit.max_hp = math.floor(cloud_damage*0.2)
        unit.turns_to_death = math.floor(cloud_duration*0.1)
        unit.spells = [StormBeam(self.get_stat("minion_range"))]
        unit.buffs = [StormElementalBuff(self)]
        self.summon(unit, target=Point(x, y))

class CurseOfRustBuff(Buff):

    def __init__(self, spell):
        self.spell = spell
        Buff.__init__(self)
    
    def on_init(self):
        self.name = "Curse of Rust"
        self.color = Tags.Metallic.color
        self.buff_type = BUFF_TYPE_CURSE
        self.owner_triggers[EventOnBuffApply] = self.on_buff_apply
    
    def on_buff_apply(self, evt):
        if isinstance(evt.buff, PetrifyBuff) or isinstance(evt.buff, GlassPetrifyBuff):
            self.owner.remove_buff(self)
            self.spell.effect(self.owner)

class WordOfRustSpell(Spell):

    def on_init(self):
        self.name = "Word of Rust"
        self.asset = ["MissingSynergies", "Icons", "word_of_rust"]
        self.tags = [Tags.Metallic, Tags.Word]
        self.level = 7
        self.max_charges = 1
        self.range = 0
        self.resistance_reduction = 50

        self.upgrades["max_charges"] = (1, 2)
        self.upgrades["resistance_reduction"] = (50, 3)
        self.upgrades["curse"] = (1, 6, "Curse of Rust", "All unaffected units other than the caster are permanently inflicted with Curse of Rust.\nWhen a cursed unit is inflicted with [petrify] or [glassify], the curse is consumed to subject it to the effects of Word of Rust.")
    
    def get_impacted_tiles(self, x, y):
        units = [unit for unit in self.caster.level.units if unit is not self.caster]
        if not self.get_stat("curse"):
            units = [unit for unit in units if Tags.Metallic in unit.tags or Tags.Glass in unit.tags or unit.has_buff(PetrifyBuff) or unit.has_buff(GlassPetrifyBuff)]
        return [Point(unit.x, unit.y) for unit in units]
    
    def get_description(self):
        return ("All [metallic] and [petrified] units other than the caster lose [{resistance_reduction}%:damage] of their [fire], [lightning], [ice], and [physical] resistances.\n"
                "All [glass] and [glassified] units other than the caster lose [{resistance_reduction}%:damage] of their [fire], [lightning], and [ice] resistances.\n"
                "A resistance will not be affected if it is negative.\n"
                "When an affected unit recovers from [petrify] or [glassify], its affected resistances will become negative.").format(**self.fmt_dict())
    
    def cast_instant(self, x, y):
        units = [unit for unit in self.caster.level.units if unit is not self.caster]
        for unit in units:
            if Tags.Metallic in unit.tags or Tags.Glass in unit.tags or unit.has_buff(PetrifyBuff) or unit.has_buff(GlassPetrifyBuff):
                self.effect(unit)
            else:
                unit.apply_buff(CurseOfRustBuff(self))
    
    def effect(self, unit):
        self.caster.level.show_effect(unit.x, unit.y, Tags.Physical)
        reduction = self.get_stat("resistance_reduction")
        for tag in [Tags.Fire, Tags.Lightning, Tags.Ice]:
            if unit.resists[tag] <= 0:
                continue
            unit.resists[tag] = math.floor(unit.resists[tag]*(1 - reduction/100))
        if Tags.Metallic in unit.tags or unit.has_buff(PetrifyBuff) and unit.resists[Tags.Physical] > 0:
            unit.resists[Tags.Physical] = math.floor(unit.resists[Tags.Physical]*(1 - reduction/100))

class SuperconductivityBuff(Buff):

    def __init__(self, spell):
        self.num_targets = spell.get_stat("num_targets")
        Buff.__init__(self)
    
    def on_init(self):
        self.name = "Superconductivity"
        self.color = Tags.Lightning.color
        self.description = "When anything other than an instance of this buff tries to deal lightning damage to this unit, shoot %i beams dealing the same damage at enemies in line of sight." % self.num_targets
        self.owner_triggers[EventOnPreDamaged] = self.on_pre_damaged
    
    def on_pre_damaged(self, evt):
        if evt.damage <= 0 or evt.damage_type != Tags.Lightning or isinstance(evt.source, SuperconductivityBuff):
            return
        targets = [unit for unit in self.owner.level.get_units_in_los(self.owner) if are_hostile(unit, self.owner) and not is_immune(unit, self, Tags.Lightning)]
        if not targets:
            return
        random.shuffle(targets)
        self.owner.level.queue_spell(self.beam(targets, evt.damage))
    
    def beam(self, targets, damage):
        for target in targets[:self.num_targets]:
            for point in Bolt(self.owner.level, self.owner, target):
                self.owner.level.deal_damage(point.x, point.y, damage, Tags.Lightning, self)
            yield

class SuperfluidityBuff(Buff):

    def __init__(self, spell):
        self.duration = spell.get_stat("duration")
        Buff.__init__(self)
        if spell.get_stat("condensate"):
            self.global_triggers[EventOnSpellCast] = self.on_spell_cast
    
    def on_init(self):
        self.name = "Superfluidity"
        self.color = Tags.Ice.color
        self.description = "When anything tries to deal ice damage to this unit, leap to a random enemy in line of sight to deal the same damage and freeze for %i turns." % self.duration
        self.owner_triggers[EventOnPreDamaged] = self.on_pre_damaged
    
    def on_pre_damaged(self, evt):
        if evt.damage <= 0 or evt.damage_type != Tags.Ice:
            return
        targets = [unit for unit in self.owner.level.get_units_in_los(self.owner) if are_hostile(unit, self.owner) and not is_immune(unit, self, Tags.Ice)]
        if not targets:
            return
        random.shuffle(targets)
        self.owner.level.queue_spell(self.leap(targets, evt.damage))
        
    def leap(self, targets, damage):

        target = None
        dest = None
        for potential_target in targets:
            if distance(potential_target, self.owner, diag=True) < 2:
                target = potential_target
                break 
            points = [point for point in list(self.owner.level.get_adjacent_points(potential_target, check_unit=True)) if self.owner.level.can_see(point.x, point.y, self.owner.x, self.owner.y)]
            if not points:
                continue
            target = potential_target
            dest = random.choice(points)
            break
        if not target:
            return
        
        if dest:
            if not self.owner.level.can_move(self.owner, dest.x, dest.y, teleport=True):
                return
            old = Point(self.owner.x, self.owner.y)
            self.owner.invisible = True
            self.owner.level.act_move(self.owner, dest.x, dest.y, teleport=True)
            for point in self.owner.level.get_points_in_line(old, dest):
                self.owner.level.leap_effect(point.x, point.y, Tags.Ice.color, self.owner)
                yield
            self.owner.invisible = False
        target.deal_damage(damage, Tags.Ice, self)
        if target.is_alive():
            target.apply_buff(FrozenBuff(), self.duration)

    def on_spell_cast(self, evt):
        if not evt.caster.is_player_controlled or Tags.Ice not in evt.spell.tags:
            return
        if not self.owner.level.can_see(evt.x, evt.y, self.owner.x, self.owner.y):
            return
        points = [point for point in self.owner.level.get_points_in_los(self.owner) if self.owner.level.can_stand(point.x, point.y, self.owner)]
        if not points:
            return
        target = min(points, key=lambda point: distance(point, Point(evt.x, evt.y)))
        self.owner.level.show_effect(self.owner.x, self.owner.y, Tags.Translocation)
        self.owner.level.act_move(self.owner, target.x, target.y, teleport=True)

class LiquidMetalBlade(Spell):

    def __init__(self, damage):
        Spell.__init__(self)
        self.damage = damage

    def on_init(self):
        self.name = "Liquid Metal Blade"
        self.description = "Hits in an arc. Deals 3 extra damage per turn of freeze on the target."
        self.range = 1.5
        self.melee = True
        self.can_target_self = False
        self.damage_type = Tags.Physical

    def get_impacted_tiles(self, x, y):
        ball = self.caster.level.get_points_in_ball(x, y, 1, diag=True)
        aoe = [p for p in ball if 1 <= distance(p, self.caster, diag=True) < 2]
        return aoe

    def cast(self, x, y):
        damage = self.get_stat("damage")
        for p in self.get_impacted_tiles(x, y):
            unit = self.caster.level.get_unit_at(p.x, p.y)
            if not unit or not are_hostile(self.caster, unit):
                self.caster.level.show_effect(p.x, p.y, Tags.Physical)
                continue
            freeze = unit.get_buff(FrozenBuff)
            bonus = freeze.turns_left*3 if freeze else 0
            unit.deal_damage(damage + bonus, Tags.Physical, self)
            yield

class LiquidMetalSpell(Spell):

    def on_init(self):
        self.name = "Liquid Metal"
        self.asset = ["MissingSynergies", "Icons", "liquid_metal"]
        self.tags = [Tags.Lightning, Tags.Ice, Tags.Metallic, Tags.Conjuration]
        self.level = 5
        self.max_charges = 3
        self.must_target_empty = True
        self.must_target_walkable = True

        self.minion_health = 30
        self.minion_damage = 9
        self.num_targets = 2
        self.duration = 3

        self.upgrades["minion_health"] = (20, 4)
        self.upgrades["num_targets"] = (1, 3, "Num Targets", "The liquid metal cube's superconductivity can shoot [1:num_targets] additional beam.")
        self.upgrades["duration"] = (2, 2, "Duration", "The liquid metal cube's superfluidity can freeze enemies for [2:duration] additional turns.")
        self.upgrades["condensate"] = (1, 4, "Quantum Condensate", "When you cast an [ice] spell, every liquid metal cube in LOS of the target point will teleport to the point in its LOS closest to the target point.")
    
    def get_description(self):
        return ("Summon a cube of superconductive, superfluid liquid metal. The cube is a stationary [metallic] [slime] minion with [{minion_health}_HP:minion_health], immunity to [ice] and [lightning], and a cleaving attack with [{minion_damage}_physical:physical] damage that deals [3:physical] extra damage per turn of [freeze] the target has.\n"
                "When anything other than an instance of this buff tries to deal [lightning] damage to the cube, it shoots [{num_targets}:num_targets] beams dealing the same damage at enemies in line of sight.\n"
                "When anything tries to deal [ice] damage to the cube, it leaps to a random enemy in line of sight to deal the same damage and [freeze] for [{duration}_turns:duration].").format(**self.fmt_dict())
    
    def get_cube(self):
        unit = GreenSlimeCube()
        unit.name = "Liquid Metal Cube"
        unit.asset = ["MissingSynergies", "Units", "liquid_metal_cube"]
        unit.tags.append(Tags.Metallic)
        unit.max_hp = self.get_stat("minion_health")
        unit.spells = [LiquidMetalBlade(self.get_stat("minion_damage"))]
        unit.buffs[0].spawner = self.get_cube
        unit.buffs.extend([SuperconductivityBuff(self), SuperfluidityBuff(self)])
        return unit
    
    def cast_instant(self, x, y):
        self.summon(self.get_cube(), Point(x, y))

class SoakedBuff(Buff):

    def __init__(self, upgrade):
        self.upgrade = upgrade
        Buff.__init__(self)
    
    def on_init(self):
        self.name = "Soaked"
        self.asset = ["MissingSynergies", "Statuses", "soaked"]
        self.color = Tags.Ice.color
        self.buff_type = BUFF_TYPE_CURSE
        self.resists[Tags.Ice] = -100
        self.resists[Tags.Lightning] = -50
        self.cascade_range = self.upgrade.get_stat("cascade_range")
        self.num_targets = self.upgrade.get_stat("num_targets")
        self.radius = self.upgrade.get_stat("radius")
        self.owner_triggers[EventOnDamaged] = self.on_damaged
        self.owner_triggers[EventOnBuffApply] = self.on_buff_apply
    
    def on_applied(self, owner):
        freeze = self.owner.get_buff(FrozenBuff)
        if freeze:
            freeze.turns_left += self.turns_left
            return ABORT_BUFF_APPLY

    def on_damaged(self, evt):
        if evt.source is self.upgrade:
            return
        if evt.damage_type == Tags.Fire:
            self.owner.level.queue_spell(self.burst(evt.damage))
            self.owner.remove_buff(self)
        elif evt.damage_type == Tags.Lightning:
            self.owner.level.queue_spell(self.bolts(evt.damage))
        else:
            self.owner.apply_buff(FrozenBuff(), self.turns_left)
            self.owner.remove_buff(self)

    def burst(self, damage):
        for stage in Burst(self.owner.level, Point(self.owner.x, self.owner.y), self.radius):
            for point in stage:
                unit = self.owner.level.get_unit_at(point.x, point.y)
                if not unit or not are_hostile(unit, self.upgrade.owner) or unit is self.owner:
                    self.owner.level.show_effect(point.x, point.y, Tags.Fire)
                else:
                    unit.deal_damage(damage//2, Tags.Fire, self.upgrade)
                    duration = self.turns_left//2
                    if duration and unit.is_alive():
                        unit.apply_buff(SoakedBuff(self.upgrade), duration)
            yield
    
    def bolts(self, damage):
        targets = [unit for unit in self.owner.level.get_units_in_ball(self.owner, self.cascade_range) if are_hostile(unit, self.upgrade.owner) and self.owner.level.can_see(self.owner.x, self.owner.y, unit.x, unit.y) and unit.has_buff(SoakedBuff) and unit is not self.owner]
        if not targets:
            return
        random.shuffle(targets)
        yield from send_bolts(lambda point: self.owner.level.show_effect(point.x, point.y, Tags.Lightning, minor=True), lambda target: self.owner.level.deal_damage(target.x, target.y, damage//2, Tags.Lightning, self.upgrade), self.owner, targets[:self.num_targets])

    def on_buff_apply(self, evt):
        if not isinstance(evt.buff, FrozenBuff):
            return
        evt.buff.turns_left += self.turns_left
        self.owner.remove_buff(self)

class Hydromancy(Upgrade):

    def on_init(self):
        self.name = "Hydromancy"
        self.asset = ["MissingSynergies", "Icons", "hydromancy"]
        self.tags = [Tags.Fire, Tags.Lightning, Tags.Ice]
        self.level = 6
        self.radius = 1
        self.num_targets = 2
        self.cascade_range = 4
        self.global_triggers[EventOnBuffRemove] = self.on_buff_remove
        self.global_triggers[EventOnDamaged] = self.on_damaged
    
    def get_description(self):
        return ("Whenever a [frozen] enemy takes [fire] or [lightning] damage, remove [freeze] from it and inflict [soaked:ice] with the same duration, giving [-100_ice:ice] and [-50_lightning:lightning] resistance.\n"
                "Whenever a [soaked:ice] unit takes [ice] damage or is [frozen], remove [soaked:ice] and inflict [freeze] or increase existing [freeze] duration on the unit by the [soaked:ice] duration.\n"
                "Whenever a [soaked:ice] unit takes [fire] damage, remove [soaked:ice] and create a steam explosion to deal half damage and inflict [soaked:ice] for half duration to other enemies in a [{radius}_tile:radius] radius around the unit.\n"
                "Whenever a [soaked:ice] unit takes [lightning] damage, deal half damage to [{num_targets}:num_targets] random [soaked:ice] enemies in LOS within [{cascade_range}_tiles:cascade_range] of the unit.\n"
                "This skill cannot trigger itself.").format(**self.fmt_dict())
    
    def on_buff_remove(self, evt):
        if not are_hostile(evt.unit, self.owner):
            return
        if not isinstance(evt.buff, FrozenBuff) or evt.buff.break_dtype != Tags.Fire:
            return
        evt.unit.apply_buff(SoakedBuff(self), evt.buff.turns_left)
    
    def on_damaged(self, evt):
        if not are_hostile(evt.unit, self.owner) or evt.damage_type != Tags.Lightning:
            return
        existing = evt.unit.get_buff(FrozenBuff)
        if not existing:
            return
        existing.break_dtype = Tags.Lightning
        evt.unit.remove_buff(existing)
        evt.unit.apply_buff(SoakedBuff(self), existing.turns_left)

class LivingLabyrinthBuff(Buff):

    def __init__(self, spell):
        self.spell = spell
        Buff.__init__(self)
    
    def on_init(self):
        self.color = Tags.Arcane.color
        self.description = "Whenever this unit attacks, each empty tile in a %i radius around itself has a 50%% chance to be randomly turned into a wall, chasm, or floor tile." % self.spell.get_stat("radius")
        self.owner_triggers[EventOnSpellCast] = lambda evt: self.owner.level.queue_spell(self.maze())
    
    def maze(self):
        yield from self.spell.maze(self.owner.x, self.owner.y)


class LivingLabyrinthSpell(Spell):

    def on_init(self):
        self.name = "Living Labyrinth"
        self.asset = ["MissingSynergies", "Icons", "living_labyrinth"]
        self.tags = [Tags.Arcane, Tags.Conjuration]
        self.level = 5
        self.max_charges = 3
        self.range = 10
        self.must_target_empty = True
        self.must_target_walkable = True
        self.requires_los = False

        self.minion_health = 45
        self.minion_damage = 12
        self.minion_range = 10
        self.radius = 4

        self.upgrades["minion_range"] = (10, 3)
        self.upgrades["minion_damage"] = (8, 2)
        self.upgrades["radius"] = (2, 3)
        self.upgrades["prison"] = (1, 5, "Living Prison", "The Living Labyrinth will no longer ensure that the mazes it creates are always escapable.\nFriends and foes alike may be trapped permanently if they do not have the ability to teleport.")

    def get_description(self):
        return ("Summon the Living Labyrinth, an [arcane] minotaur with [{minion_health}_HP:minion_health], and a teleport attack with [{minion_range}_range:minion_range] that deals [{minion_damage}_arcane:arcane] damage.\n"
                "Whenever the Living Labyrinth attacks, each empty tile in a [{radius}_radius:radius] around it has a [50%:arcane] chance to be randomly turned into a wall, chasm, or floor tile.\n"
                "For the safety of its summoner, the Living Labyrinth will always ensure that the mazes it creates are escapable.\n"
                "Casting this spell again while the Living Labyrinth is already present will instead teleport it to the target tile, restore it to full HP, and immediately transform its surroundings into a maze.").format(**self.fmt_dict())

    def maze(self, x, y):
        for point in self.caster.level.get_points_in_ball(x, y, self.get_stat("radius")):
            if random.random() < 0.5 and not self.caster.level.get_unit_at(point.x, point.y) and not self.caster.level.tiles[point.x][point.y].prop:
                func = random.choice([self.caster.level.make_wall, self.caster.level.make_chasm, self.caster.level.make_floor])
                func(point.x, point.y)
        if not self.get_stat("prison"):
            self.caster.level.gen_params.ensure_connectivity()
            self.caster.level.gen_params.ensure_connectivity(chasm=True)
        yield

    def cast_instant(self, x, y):

        existing = None
        for unit in self.caster.level.units:
            if unit.source is self:
                existing = unit
                break
        if existing:
            existing.deal_damage(existing.cur_hp - existing.max_hp, Tags.Heal, self)
            if self.caster.level.can_move(existing, x, y, teleport=True):
                self.caster.level.show_effect(existing.x, existing.y, Tags.Translocation)
                self.caster.level.act_move(existing, x, y, teleport=True)
            self.caster.level.queue_spell(self.maze(x, y))
            return
        
        unit = Unit()
        unit.unique = True
        unit.name = "The Living Labyrinth"
        unit.asset = ["MissingSynergies", "Units", "living_labyrinth"]
        unit.tags = [Tags.Living, Tags.Arcane]
        unit.resists[Tags.Arcane] = 100
        unit.max_hp = self.get_stat("minion_health")
        leap = LeapAttack(damage=self.get_stat("minion_damage"), damage_type=Tags.Arcane, range=self.get_stat("minion_range"), is_ghost=True)
        leap.name = "Phase Charge"
        melee = SimpleMeleeAttack(damage=self.get_stat("minion_damage", base=8), damage_type=Tags.Arcane, trample=True)
        unit.spells = [leap, melee]
        unit.buffs = [LivingLabyrinthBuff(self)]
        self.summon(unit, target=Point(x, y))

class AgonizingPowerBuff(Buff):
    def on_init(self):
        self.name = "Agonizing Power"
        self.color = Tags.Dark.color
        self.spell_bonuses[AgonizingStormSpell]["radius"] = 1
        self.stack_type = STACK_INTENSITY
    def on_advance(self):
        if not self.owner.has_buff(ChannelBuff):
            self.owner.remove_buff(self)

class AgonizingStormSpell(Spell):

    def on_init(self):
        self.name = "Agonizing Storm"
        self.asset = ["MissingSynergies", "Icons", "agonizing_storm"]
        self.tags = [Tags.Dark, Tags.Lightning, Tags.Sorcery]
        self.level = 5
        self.max_charges = 3
        self.range = 0

        self.radius = 6
        self.damage = 17
        self.duration = 3

        self.upgrades["damage"] = (7, 4)
        self.upgrades["radius"] = (4, 3)
        self.upgrades["duration"] = (2, 2)
        self.upgrades["deep"] = (1, 5, "Deep Agony", "Agonizing Storm penetrates enemy [dark] and [lightning] resistances by a percentage equal to your percentage of missing HP.")
    
    def get_description(self):
        return ("Channel to target enemies in a [{radius}_tile:radius] radius, increasing by 1 per turn channeled.\n"
                "[Stunned] enemies lose [stun] and take [{damage}_lightning:lightning] damage plus [1:lightning] per turn removed.\n"
                "[Berserk] enemies lose [berserk] and take [{damage}_dark:dark] damage plus [1:dark] per turn removed.\n"
                "Enemies that are neither [stunned] or [berserk] are randomly inflicted with [stun] or [berserk] for [{duration}_turns:duration].\n"
                "You have a 50% chance to randomly take [1_dark:dark] or [1_lightning:lightning] damage for each enemy targeted.").format(**self.fmt_dict())

    def cast(self, x, y, channel_cast=False):

        if not channel_cast:
            self.caster.apply_buff(ChannelBuff(self.cast, Point(x, y)))
            return
        
        self.caster.apply_buff(AgonizingPowerBuff())
        damage = self.get_stat("damage")
        duration = self.get_stat("duration")
        penetration = math.ceil((self.caster.max_hp - self.caster.cur_hp)/self.caster.max_hp*100) if self.get_stat("deep") else 0

        effects_left = 7

        for unit in [unit for unit in self.caster.level.get_units_in_ball(self.caster, self.get_stat("radius")) if are_hostile(self.caster, unit)]:
            if random.random() < 0.5:
                self.caster.deal_damage(1, random.choice([Tags.Dark, Tags.Lightning]), self)
            effects_left += 1
            stun = unit.get_buff(Stun)
            berserk = unit.get_buff(BerserkBuff)
            if not stun and not berserk:
                debuff_type = random.choice([Stun, BerserkBuff])
                unit.apply_buff(debuff_type(), duration)
                continue
            if stun:
                unit.remove_buff(stun)
                unit.resists[Tags.Lightning] -= penetration
                unit.deal_damage(damage + stun.turns_left, Tags.Lightning, self)
                unit.resists[Tags.Lightning] += penetration
            if berserk:
                unit.remove_buff(berserk)
                unit.resists[Tags.Dark] -= penetration
                unit.deal_damage(damage + berserk.turns_left, Tags.Dark, self)
                unit.resists[Tags.Dark] += penetration

        if effects_left <= 0:
            return

        # Show some graphical indication of this aura if it didnt hit much
        points = self.caster.level.get_points_in_ball(self.caster.x, self.caster.y, self.get_stat("radius"))
        points = [p for p in points if not self.caster.level.get_unit_at(p.x, p.y)]
        random.shuffle(points)
        for _ in range(effects_left):
            if not points:
                break
            p = points.pop()
            self.caster.level.show_effect(p.x, p.y, random.choice([Tags.Dark, Tags.Lightning]), minor=True)

        yield

class NuclearWinter(Upgrade):

    def on_init(self):
        self.name = "Nuclear Winter"
        self.asset = ["MissingSynergies", "Icons", "nuclear_winter"]
        self.tags = [Tags.Lightning, Tags.Ice, Tags.Nature]
        self.level = 4
        self.damage = 5
    
    def get_description(self):
        return ("Each turn, enemies inside thunderstorm and blizzard clouds take [{damage}_poison:poison] damage.").format(**self.fmt_dict())

    def on_advance(self):
        damage = self.get_stat("damage")
        for unit in [unit for unit in list(self.owner.level.units) if are_hostile(unit, self.owner)]:
            cloud = self.owner.level.tiles[unit.x][unit.y].cloud
            if isinstance(cloud, StormCloud) or isinstance(cloud, BlizzardCloud):
                unit.deal_damage(damage, Tags.Poison, self)

class DeliriumBuff(Buff):

    def __init__(self, source, weakness=False):
        Buff.__init__(self)
        self.source = source
        self.weakness = weakness
        if weakness:
            self.resists[Tags.Arcane] = -10
    
    def on_init(self):
        self.name = "Delirium"
        self.buff_type = BUFF_TYPE_CURSE
        self.stack_type = STACK_INTENSITY
        self.asset = ["MissingSynergies", "Statuses", "delirium"]
        self.color = Tags.Arcane.color
        self.global_bonuses["damage"] = -1
    
    def on_applied(self, owner):
        self.duration = self.turns_left

    def on_unapplied(self):
        self.owner.apply_buff(WithdrawalBuff(self.source, self.weakness), self.duration)

class WithdrawalBuff(Buff):

    def __init__(self, source, weakness=False):
        Buff.__init__(self)
        self.source = source
        if weakness:
            self.resists[Tags.Poison] = -10

    def on_init(self):
        self.name = "Withdrawal"
        self.buff_type = BUFF_TYPE_CURSE
        self.stack_type = STACK_INTENSITY
        self.asset = ["MissingSynergies", "Statuses", "withdrawal"]
        self.color = Tags.Poison.color
    
    def on_advance(self):
        self.owner.deal_damage(1, Tags.Poison, self.source)
        self.owner.deal_damage(1, Tags.Arcane, self.source)

class PsychedelicPuff(SimpleRangedAttack):

    def __init__(self, damage, range, duration, weakness=False):
        self.weakness = weakness
        self.duration = duration
        SimpleRangedAttack.__init__(self, name="Psychedelic Puff", damage=damage, damage_type=None, range=range, radius=1, cool_down=3, effect=[Tags.Poison, Tags.Arcane])
    
    def get_description(self):
        return "Deals poison and arcane damage and inflicts %i turns of delirium to enemies." % self.get_stat("duration")

    def hit(self, x, y):
        unit = self.caster.level.get_unit_at(x, y)
        if not unit or not are_hostile(unit, self.caster):
            self.caster.level.show_effect(x, y, Tags.Poison)
            self.caster.level.show_effect(x, y, Tags.Arcane)
            return
        damage = self.get_stat("damage")
        unit.deal_damage(damage, Tags.Poison, self)
        unit.deal_damage(damage, Tags.Arcane, self)
        if unit.is_alive():
            unit.apply_buff(DeliriumBuff(self, self.weakness), self.get_stat("duration"))

class PsychedelicMushboomBuff(MushboomBuff):

    def __init__(self, spell):
        MushboomBuff.__init__(self, lambda: DeliriumBuff(self, spell.get_stat("weakness")), spell.get_stat("duration"))
        self.description = "On death, applies %d turns of %s to adjacent enemies." % (self.apply_duration, self.buff().name)

    def explode(self, level, x, y):
        for p in level.get_points_in_rect(x - 1, y - 1, x + 1, y + 1):
            level.show_effect(p.x, p.y, Tags.Poison)
            level.show_effect(p.x, p.y, Tags.Arcane)
            unit = level.get_unit_at(p.x, p.y)
            if unit and are_hostile(unit, self.owner):
                unit.apply_buff(self.buff(), self.apply_duration)
        yield

class PsychedelicSporesSpell(Spell):

    def on_init(self):
        self.name = "Psychedelic Spores"
        self.asset = ["MissingSynergies", "Icons", "psychedelic_spores"]
        self.tags = [Tags.Arcane, Tags.Nature, Tags.Conjuration]
        self.level = 4
        self.max_charges = 4
        self.range = 8

        self.minion_health = 66
        self.minion_damage = 2
        self.minion_range = 2
        self.duration = 5

        self.must_target_empty = True
        self.must_target_walkable = True

        self.upgrades["minion_damage"] = (4, 3)
        self.upgrades["minion_range"] = (2, 2)
        self.upgrades["duration"] = (3, 3)
        self.upgrades["regen"] = (1, 3, "Regeneration", "Giant psychedelic mushbooms regenerate [6_HP:heal] per turn.")
        self.upgrades["weakness"] = (1, 5, "Mind Wilt", "Delirium makes enemies lose [10_arcane:arcane] resistance per stack.\nWithdrawal makes enemies lose [10_poison:poison] resistance per stack.")
    
    def get_description(self):
        return ("Summon a giant psychedelic mushboom with [{minion_health}_HP:minion_health].\n"
                "It has an attack with [{minion_range}_range:minion_range], [1_radius:radius], and [3_turns:duration] cooldown that deals [{minion_damage}_poison:poison] and [{minion_damage}_arcane:arcane] damage and inflicts a stack of delirium for [{duration}_turns:duration] to enemies.\n"
                "On death, it applies a stack of delirium with the same duration to adjacent enemies.\n"
                "An enemy with delirium suffers a [-1:damage] penalty to all spell damage per stack.\n"
                "When delirium is removed, it applies a stack of withdrawal, inflicting [1_poison:poison] and [1_arcane:arcane] damage per turn per stack.").format(**self.fmt_dict())

    def cast_instant(self, x, y):
        unit = Unit()
        unit.asset = ["MissingSynergies", "Units", "giant_psychedelic_mushboom"]
        unit.name = "Giant Psychedelic Mushboom"
        unit.max_hp = self.get_stat("minion_health")
        unit.tags = [Tags.Nature, Tags.Arcane]
        unit.resists[Tags.Fire] = -50
        unit.resists[Tags.Ice] = -50
        unit.resists[Tags.Poison] = 100
        unit.resists[Tags.Arcane] = 100
        unit.spells = [PsychedelicPuff(self.get_stat("minion_damage"), self.get_stat("minion_range"), self.get_stat("duration"), self.get_stat("weakness"))]
        unit.buffs = [PsychedelicMushboomBuff(self)]
        if self.get_stat("regen"):
            unit.buffs.append(RegenBuff(6))
        self.summon(unit, target=Point(x, y))

class GoldPrecipitationBuff(Buff):

    def __init__(self, spell):
        self.spell = spell
        Buff.__init__(self)
    
    def on_init(self):
        self.name = "Gold Precipitation"
        self.color = Tags.Holy.color
        self.buff_type = BUFF_TYPE_CURSE
        self.owner_triggers[EventOnDeath] = self.on_death
    
    def make_slime(self):
        unit = Unit()
        unit.name = "Gold Slime"
        unit.asset = ["MissingSynergies", "Units", "gold_slime"]
        unit.tags = [Tags.Slime, Tags.Metallic, Tags.Holy]
        unit.resists[Tags.Holy] = 100
        unit.max_hp = self.spell.get_stat("minion_health", base=10)
        unit.spells = [SimpleMeleeAttack(damage=self.spell.get_stat("minion_damage", base=3), damage_type=Tags.Holy)]
        unit.buffs = [SlimeBuff(self.make_slime)]
        return unit

    def on_death(self, evt):
        if random.random() >= 0.5:
            return
        self.spell.summon(self.make_slime(), target=self.owner, radius=5)

class KingswaterSpell(Spell):

    def on_init(self):
        self.name = "Kingswater"
        self.asset = ["MissingSynergies", "Icons", "kingswater"]
        self.tags = [Tags.Holy, Tags.Nature, Tags.Sorcery]
        self.level = 2
        self.max_charges = 14

        self.range = 8
        self.radius = 2
        self.damage = 14
        self.duration = 3

        self.upgrades["max_charges"] = (7, 2)
        self.upgrades["radius"] = (1, 3)
        self.upgrades["poison"] = (1, 4, "Vitriol", "Kingswater also deals [poison] damage.")
        self.upgrades["precipitate"] = (1, 5, "Gold Precipitate", "[Metallic], [glass], [petrified], or [glassified] enemies are inflicted with Gold Precipitation.\nWhen an enemy with Gold Precipitation dies, you have a 50% chance to summon a gold slime near it.")
    
    def get_impacted_tiles(self, x, y):
        return [p for stage in Burst(self.caster.level, Point(x, y), self.get_stat('radius')) for p in stage]

    def get_description(self):
        return ("Remove all buffs from enemies in a [{radius}_tile:radius] burst and [blind] them for [{duration}_turns:duration].\n"
                "If an enemy is [metallic], [glass], [petrified], or [glassified], it is [acidified:poison], losing [100_poison:poison] resistance, and takes [{damage}_holy:holy] damage.").format(**self.fmt_dict())

    def hit(self, x, y, damage, duration, poison, precipitate):
        self.caster.level.show_effect(x, y, Tags.Holy, minor=True)
        self.caster.level.show_effect(x, y, Tags.Poison, minor=True)
        unit = self.caster.level.get_unit_at(x, y)
        if not unit or not are_hostile(unit, self.caster):
            return
        for buff in unit.buffs:
            if buff.buff_type == BUFF_TYPE_BLESS:
                unit.remove_buff(buff)
        unit.apply_buff(BlindBuff(), duration)
        if Tags.Metallic in unit.tags or Tags.Glass in unit.tags or unit.has_buff(PetrifyBuff) or unit.has_buff(GlassPetrifyBuff):
            unit.apply_buff(Acidified())
            if precipitate:
                unit.apply_buff(GoldPrecipitationBuff(self))
            unit.deal_damage(damage, Tags.Holy, self)
            if poison:
                unit.deal_damage(damage, Tags.Poison, self)

    def cast(self, x, y):
        damage = self.get_stat("damage")
        duration = self.get_stat("duration")
        poison = self.get_stat("poison")
        precipitate = self.get_stat("precipitate")
        for stage in Burst(self.caster.level, Point(x, y), self.get_stat("radius")):
            for point in stage:
                self.hit(point.x, point.y, damage, duration, poison, precipitate)
            yield

class ChaosTheoryCloudburst(Spell):

    def __init__(self, spell):
        self.spell = spell
        Spell.__init__(self)

    def on_init(self):
        self.name = "Cloudburst"
        self.range = 0
        self.cool_down = 3
    
    def get_description(self):
        num_targets = self.spell.get_stat("num_targets")
        radius = self.spell.get_stat("radius")
        return "Teleport to a random thunderstorm or blizzard cloud. Create clouds on %i to %i random tiles within %i radius or cause existing clouds to explode into %i radius bursts that deal arcane damage to enemies and melt walls." % (num_targets, num_targets*2, radius*2, radius)

    def can_cast(self, x, y):
        if not self.get_clouds():
            return False
        return Spell.can_cast(self, x, y)

    def get_clouds(self):
        clouds = [cloud for cloud in self.caster.level.clouds if isinstance(cloud, StormCloud) or isinstance(cloud, BlizzardCloud)]
        return [cloud for cloud in clouds if self.caster.level.can_move(self.caster, cloud.x, cloud.y, teleport=True)]

    def cast_instant(self, x, y):
        clouds = self.get_clouds()
        if not clouds:
            return
        self.spell.cloudburst(self.caster, random.choice(clouds))

class ChaosTheoryPerturbation(Spell):

    def __init__(self, spell):
        self.spell = spell
        Spell.__init__(self)
    
    def on_init(self):
        self.name = "Perturbation"
        self.radius = 2
        self.damage = self.spell.get_stat("minion_damage")
        self.range = self.spell.get_stat("minion_range")
        self.requires_los = False
        self.damage_type = Tags.Arcane
        self.description = "Only damages enemies. Melts walls and creates thunderstorm and blizzard clouds."

    def get_impacted_tiles(self, x, y):
        return [p for stage in Burst(self.caster.level, Point(x, y), self.get_stat('radius'), ignore_walls=True) for p in stage]
    
    def can_redeal(self, unit):
        return not is_immune(unit, self, Tags.Lightning) or not is_immune(unit, self, Tags.Ice)

    def cast(self, x, y):
        for point in Bolt(self.caster.level, self.caster, Point(x, y), find_clear=False):
            self.caster.level.show_effect(point.x, point.y, Tags.Arcane, minor=True)
            yield
        damage = self.get_stat("damage")
        for stage in Burst(self.caster.level, Point(x, y), self.get_stat("radius"), ignore_walls=True):
            for point in stage:
                unit = self.caster.level.get_unit_at(point.x, point.y)
                if not unit or not are_hostile(self.caster, unit):
                    self.caster.level.show_effect(point.x, point.y, Tags.Arcane)
                else:
                    unit.deal_damage(damage, Tags.Arcane, self)
                if self.caster.level.tiles[point.x][point.y].is_wall():
                    self.caster.level.make_floor(point.x, point.y)
                self.spell.make_cloud(self.caster, point)
            yield

class ChaosTheorySpell(Spell):

    def on_init(self):
        self.name = "Chaos Theory"
        self.asset = ["MissingSynergies", "Icons", "chaos_theory"]
        self.tags = [Tags.Arcane, Tags.Ice, Tags.Chaos, Tags.Conjuration]
        self.level = 5
        self.max_charges = 2
        self.range = RANGE_GLOBAL
        self.requires_los = False
        self.must_target_empty = True

        self.num_targets = 4
        self.radius = 4
        self.damage = 5
        self.duration = 5
        self.minion_damage = 9
        self.minion_range = 7
        self.minion_health = 50
        self.shields = 3

        self.upgrades["radius"] = (2, 6, "Radius", "The Butterfly Effect's cloud explosions have [2:radius] more radius.\nThe area in which it can creates clouds and explosions has [4:radius] more radius.")
        self.upgrades["num_targets"] = (2, 4, "Num Targets", "The Butterfly Effect can now create [6:num_targets] to [12:num_targets] clouds or explosions around itself.")
        self.upgrades["shields"] = (3, 2)
        self.upgrades["max_charges"] = (6, 2)
    
    def fmt_dict(self):
        stats = Spell.fmt_dict(self)
        stats["double_radius"] = self.get_stat("radius")*2
        stats["double_num_targets"] = self.get_stat("num_targets")*2
        return stats

    def get_description(self):
        return ("Summon the Butterfly Effect, a [demon] minion that creates thunderstorm and blizzard clouds.\n"
                "Every [3_turns:duration], the Butterfly Effect teleports to a random cloud, and targets [{num_targets}:num_targets] to [{double_num_targets}:num_targets] random tiles in a [{double_radius}_radius:radius] around itself. If a target tile has a cloud, consume the cloud to deal [arcane] damage in a [{radius}_tile:radius] burst equal to the cloud's damage times strikechance and melt walls. Otherwise create a cloud.\n"
                "Casting this spell again when the Butterfly Effect is already present will instead teleport it to the target tile, restore it to at least [{shields}_SH:shields], and immediately use its cloudburst.").format(**self.fmt_dict())

    def get_existing(self):
        for unit in self.caster.level.units:
            if unit.source is self:
                return unit
        return None

    def cloudburst(self, minion, target):
        if self.caster.level.can_move(minion, target.x, target.y, teleport=True):
            self.caster.level.show_effect(minion.x, minion.y, Tags.Translocation)
            self.caster.level.act_move(minion, target.x, target.y, teleport=True)
        radius = self.get_stat("radius")
        points = [p for p in self.caster.level.get_points_in_ball(target.x, target.y, radius*2) if not self.caster.level.tiles[p.x][p.y].is_wall()]
        if not points:
            return
        random.shuffle(points)
        num_targets = self.get_stat("num_targets")
        for point in points[:random.choice(list(range(num_targets, num_targets*2 + 1)))]:
            cloud = self.caster.level.tiles[point.x][point.y].cloud
            damage = 0
            if isinstance(cloud, StormCloud):
                damage = cloud.damage*cloud.strikechance
            elif isinstance(cloud, BlizzardCloud):
                damage = cloud.damage
            if damage:
                cloud.kill()
                self.caster.level.queue_spell(self.boom(point.x, point.y, damage, radius))
            else:
                self.make_cloud(minion, point)

    def make_cloud(self, minion, point):
        cloud_damage = self.get_stat("damage")
        cloud_duration = self.get_stat("duration")
        flip = random.choice([True, False])
        if flip:
            cloud = StormCloud(minion, cloud_damage*2)
        else:
            cloud = BlizzardCloud(minion, cloud_damage)
        cloud.source = self
        cloud.duration = cloud_duration
        self.caster.level.add_obj(cloud, point.x, point.y)

    def boom(self, x, y, damage, radius):
        for stage in Burst(self.caster.level, Point(x, y), radius, ignore_walls=True):
            for point in stage:
                unit = self.caster.level.get_unit_at(point.x, point.y)
                if not unit or not are_hostile(unit, self.caster):
                    self.caster.level.show_effect(point.x, point.y, Tags.Arcane)
                else:
                    unit.deal_damage(damage, Tags.Arcane, self)
                if self.caster.level.tiles[point.x][point.y].is_wall():
                    self.caster.level.make_floor(point.x, point.y)
            yield

    def cast_instant(self, x, y):
        
        existing = self.get_existing()
        if existing:
            existing.shields = max(self.get_stat("shields"), existing.shields)
            self.cloudburst(existing, Point(x, y))
            return
        
        unit = Unit()
        unit.unique = True
        unit.name = "The Butterfly Effect"
        unit.asset = ["MissingSynergies", "Units", "the_butterfly_effect"]
        unit.tags = [Tags.Chaos, Tags.Arcane, Tags.Ice, Tags.Demon]
        unit.max_hp = self.get_stat("minion_health")
        unit.shields = self.get_stat("shields")
        unit.resists[Tags.Arcane] = 100
        unit.resists[Tags.Ice] = 100
        unit.resists[Tags.Lightning] = 100
        unit.flying = True
        unit.spells = [ChaosTheoryCloudburst(self), ChaosTheoryPerturbation(self)]
        self.summon(unit, target=Point(x, y))

class AfterlifeEchoesBuff(Buff):

    ECHO_LIFE = 1
    ECHO_SPIRIT = 2
    ECHO_ELEMENTAL = 3
    ECHO_SHATTERING = 4

    def __init__(self, spell):
        self.spell = spell
        Buff.__init__(self)
    
    def on_init(self):
        self.name = "Afterlife Echoes"
        self.color = Tags.Dark.color
        self.radius = self.spell.get_stat("radius")
        if self.spell.get_stat("life"):
            self.echo_type = self.ECHO_LIFE
        elif self.spell.get_stat("spirit"):
            self.echo_type = self.ECHO_SPIRIT
        elif self.spell.get_stat("elemental"):
            self.echo_type = self.ECHO_ELEMENTAL
        elif self.spell.get_stat("shattering"):
            self.echo_type = self.ECHO_SHATTERING
        else:
            self.echo_type = None
        if self.spell.get_stat("myriad"):
            self.global_bonuses["num_summons"] = 1
        self.global_triggers[EventOnUnitAdded] = lambda evt: self.owner.level.queue_spell(self.boom(evt.unit))

    def boom(self, unit):

        if are_hostile(unit, self.owner) or unit.is_player_controlled or unit.source is self.spell:
            return
        
        if self.echo_type == self.ECHO_ELEMENTAL:
            spells = []
            if Tags.Fire in unit.tags:
                spells.append(FireballSpell())
            if Tags.Lightning in unit.tags:
                spells.append(LightningBoltSpell())
            if Tags.Ice in unit.tags:
                spells.append(Icicle())
            for spell in spells:
                spell.statholder = self.owner
                spell.owner = unit
                spell.caster = unit
                spell.max_charges = 0
                spell.cur_charges = 0
            if spells:
                hp_left = unit.max_hp
                while hp_left > 0:
                    chance = min(20, hp_left)/20
                    hp_left -= 20
                    if random.random() >= chance:
                        continue
                    random.shuffle(spells)
                    can_cast = False
                    for spell in spells:
                        targets = [u for u in list(self.owner.level.units) if are_hostile(u, self.owner) and spell.can_cast(u.x, u.y)]
                        if not targets:
                            continue
                        can_cast = True
                        target = random.choice(targets)
                        self.owner.level.act_cast(unit, spell, target.x, target.y, pay_costs=False)
                        break
                    if not can_cast:
                        break

        life = (self.echo_type == self.ECHO_LIFE) and (Tags.Nature in unit.tags or Tags.Living in unit.tags)
        damage = unit.max_hp//2
        for stage in Burst(self.owner.level, Point(unit.x, unit.y), self.radius):
            for p in stage:
                target = self.owner.level.get_unit_at(p.x, p.y)
                if not target or not are_hostile(target, self.owner):
                    self.owner.level.show_effect(p.x, p.y, Tags.Dark)
                    self.owner.level.show_effect(p.x, p.y, Tags.Holy)
                    if life:
                        self.owner.level.show_effect(p.x, p.y, Tags.Poison)
                else:
                    target.deal_damage(damage, Tags.Dark, self.spell)
                    target.deal_damage(damage, Tags.Holy, self.spell)
                    if life:
                        poison = target.get_buff(Poison)
                        if poison:
                            poison.turns_left += damage
                        else:
                            target.apply_buff(Poison(), damage)
            yield
        
        self.owner.level.queue_spell(self.kill_unit(unit))
    
    def kill_unit(self, unit):

        existing = unit.get_buff(ReincarnationBuff)
        if existing:
            existing.lives += 1
        else:
            unit.apply_buff(ReincarnationBuff())
        point = Point(unit.x, unit.y)
        unit.cur_hp = 0
        unit.kill()

        if self.echo_type == self.ECHO_SPIRIT and [tag for tag in [Tags.Holy, Tags.Demon, Tags.Undead] if tag in unit.tags]:
            shade = Unit()
            shade.name = "Afterlife Shade"
            shade.asset = ["MissingSynergies", "Units", "afterlife_shade"]
            shade.tags = [Tags.Holy, Tags.Demon, Tags.Undead]
            shade.max_hp = unit.max_hp
            shade.resists[Tags.Holy] = 100
            shade.resists[Tags.Poison] = 100
            shade.flying = True
            shade.spells = [AfterlifeShadeBolt(unit.max_hp//10, self.spell.get_stat("minion_range", base=5))]
            self.spell.summon(shade, target=point, radius=5)
            return
        
        if self.echo_type == self.ECHO_SHATTERING and [tag for tag in [Tags.Arcane, Tags.Metallic, Tags.Glass] if tag in unit.tags]:
            shards = math.ceil(unit.max_hp/20 + unit.shields/2)
            for _ in range(shards):
                shard = Unit()
                shard.name = "Soul Shard"
                shard.asset = ["MissingSynergies", "Units", "soul_shard"]
                shard.tags = [Tags.Arcane, Tags.Metallic, Tags.Glass]
                shard.max_hp = 1
                shard.shields = 1
                for tag in [Tags.Fire, Tags.Ice, Tags.Lightning, Tags.Poison, Tags.Holy, Tags.Dark, Tags.Arcane, Tags.Physical]:
                    shard.resists[tag] = 0
                shard.flying = True
                shard.stationary = True
                shard.buffs = [SoulShardBuff(), TeleportyBuff()]
                self.spell.summon(shard, target=point, radius=5, sort_dist=False)

        yield

class AfterlifeShadeBolt(SimpleRangedAttack):
    def __init__(self, damage, range):
        SimpleRangedAttack.__init__(self, "Twilight Bolt", damage=damage, damage_type=[Tags.Holy, Tags.Dark], range=range)
        self.description = "Deals both damage types."
    def hit(self, x, y):
        damage = self.get_stat("damage")
        self.caster.level.deal_damage(x, y, damage, Tags.Dark, self)
        self.caster.level.deal_damage(x, y, damage, Tags.Holy, self)

class SoulShardBuff(Buff):
    def on_init(self):
        self.name = "Soul Shard"
        self.color = Tags.Glass.color
        self.description = "When hit by an enemy, deal 2 arcane or 2 physical damage to that enemy."
        self.owner_triggers[EventOnPreDamaged] = self.on_pre_damaged
    def on_pre_damaged(self, evt):
        if evt.damage <= 0 or not evt.source or not evt.source.owner or not are_hostile(evt.source.owner, self.owner):
            return
        evt.source.owner.deal_damage(2, random.choice([Tags.Arcane, Tags.Physical]), self)

class AfterlifeEchoesSpell(Spell):

    def on_init(self):
        self.name = "Afterlife Echoes"
        self.asset = ["MissingSynergies", "Icons", "afterlife_echoes"]
        self.tags = [Tags.Holy, Tags.Dark, Tags.Enchantment]
        self.level = 4
        self.max_charges = 3
        self.range = 0

        self.duration = 15
        self.radius = 2

        self.upgrades["duration"] = (15, 2)
        self.upgrades["radius"] = (1, 4)
        self.upgrades["myriad"] = (1, 5, "Myriad Souls", "For the duration, spells and skills that summon multiple minions will summon [1:num_summons] more minion.")
        self.upgrades["life"] = (1, 5, "Life Echoes", "When you summon a [living] or [nature] minion, that minion's death explosion will [poison] enemies for a number of turns equal to 50% of its max HP, stacking in duration with any existing [poison] they have.", "echo")
        self.upgrades["spirit"] = (1, 5, "Spirit Echoes", "When you summon a [holy], [demon], or [undead] minion, that minion's death explosion will summon an Afterlife Shade with the same max HP.\nThe Afterlife Shade has an attack with [5_range:minion_range] that deals [holy] and [dark] damage equal to 10% of its max HP.", "echo")
        self.upgrades["elemental"] = (1, 5, "Elemental Echoes", "When you summon a [fire], [lightning], or [ice] minion, that minion's death explosion has a chance to cast Fireball, Lightning Bolt, or Icicle respectively at valid enemy targets. A minion with multiple tags will cast one of the spells at random.\nThe chance to cast is the minion's max HP divided by 20, with an extra guaranteed cast per 20 HP the minion has.\nThese spells gain all of your upgrades and bonuses.", "echo")
        self.upgrades["shattering"] = (1, 5, "Shattering Echoes", "When you summon an [arcane], [metallic], or [glass] minion, that minion's death explosion will summon a Soul Shard for every 20 HP and [2_SH:shields] the minion has, rounded up.\nSoul Shards have fixed 1 HP and [1_SH:shields]. They deal [2_physical:physical] or [2_arcane:arcane] damage to enemies that hit them.", "echo")

    def get_impacted_tiles(self, x, y):
        return [Point(self.caster.x, self.caster.y)]

    def get_description(self):
        return ("Whenever you summon a minion from any source other than this spell, that minion gains 1 reincarnation, then immediately dies.\n"
                "This death creates an explosion that deals [holy] and [dark] damage to enemies in a [{radius}_tile:radius] burst. The damage dealt is equal to half of the minion's max HP.\n"
                "Lasts [{duration}_turns:duration].").format(**self.fmt_dict())

    def cast_instant(self, x, y):
        self.caster.apply_buff(AfterlifeEchoesBuff(self), self.get_stat("duration"))

class TimeDilationSpell(Spell):

    def on_init(self):
        self.name = "Time Dilation"
        self.asset = ["MissingSynergies", "Icons", "time_dilation"]
        self.tags = [Tags.Arcane, Tags.Enchantment]
        self.level = 3
        self.max_charges = 3
        self.requires_los = False
        self.range = 8
        self.radius = 2
        self.turns = 3

        self.upgrades["radius"] = (2, 3)
        self.upgrades["max_charges"] = (6, 3)
        self.upgrades["turns"] = (2, 3, "More Turns", "The affected buffs, debuffs, and passive effects advance by [2:duration] more turns without losing duration.")
        self.upgrades["selective"] = (1, 3, "Selective Dilation", "Time Dilation no longer affects the debuffs of allies, or the buffs and passive effects of enemies.")
        self.upgrades["self"] = (1, 4, "Self Dilation", "You can now target yourself with Time Dilation to affect yourself.\nThis consumes 2 extra charges of the spell and cannot be done if you have less than 3 charges remaining.")

    def get_description(self):
        return ("Trigger the per-turn effects of the buffs, debuffs, and passive effects of all units in a [{radius}_tile:radius] radius [{turns}_times:duration], without losing any of their actual remaining durations.\nThe caster is unaffected.").format(**self.fmt_dict())

    def can_cast(self, x, y):
        if x == self.caster.x and y == self.caster.y and self.get_stat("self") and self.cur_charges >= 3:
            return True
        return Spell.can_cast(self, x, y)

    def get_impacted_tiles(self, x, y):
        if x == self.caster.x and y == self.caster.y:
            return [Point(x, y)]
        return Spell.get_impacted_tiles(self, x, y)

    def cast_instant(self, x, y):

        turns = self.get_stat("turns")
        selective = self.get_stat("selective")

        if x == self.caster.x and y == self.caster.y:
            self.caster.level.show_effect(x, y, Tags.Arcane)
            self.cur_charges -= 2
            for buff in self.caster.buffs:
                if selective and buff.buff_type == BUFF_TYPE_CURSE:
                    continue
                for _ in range(turns):
                    buff.on_advance()
            return
        
        for unit in self.caster.level.get_units_in_ball(Point(x, y), self.get_stat("radius")):
            if unit is self.caster:
                continue
            self.caster.level.show_effect(unit.x, unit.y, Tags.Arcane)
            for buff in unit.buffs:
                if selective and (are_hostile(self.caster, unit) == (buff.buff_type != BUFF_TYPE_CURSE)):
                    continue
                for _ in range(turns):
                    buff.on_advance()

class CultOfDarknessPassive(Buff):

    def __init__(self, spell):
        self.spell = spell
        Buff.__init__(self)
        self.buff_type = BUFF_TYPE_PASSIVE
        self.stack_type = STACK_REPLACE
    
    def on_init(self):
        self.death = self.spell.get_stat("death")
        self.salvation = self.spell.get_stat("salvation")
        self.torment = self.spell.get_stat("torment")
        self.counter = 0
        self.global_triggers[EventOnDeath] = self.on_death

    def get_tormentor(self, unit):
        unit.spells[0].radius = self.spell.get_stat("radius", base=4)
        return unit
    
    def raise_skeleton(self, unit):
        skeleton = mods.BugsAndScams.Bugfixes.raise_skeleton(self.owner, unit, self.spell, summon=False)
        if not skeleton:
            return
        skeleton.max_hp *= 2
        skeleton.spells[0].damage = self.spell.get_stat("minion_damage", base=5)
        self.spell.summon(skeleton, target=unit, radius=0)
        yield

    def on_death(self, evt):

        if evt.unit.source is not self.spell:
            return

        if self.torment and (Tags.Living in evt.unit.tags or Tags.Undead in evt.unit.tags):
            self.counter += 1
            if self.counter >= 66:
                self.counter = 0
                mass = DarkTormentorMass()
                mass.buffs[0].spawner = lambda: self.get_tormentor(DarkTormentor())
                apply_minion_bonuses(self.spell, mass)
                self.spell.summon(mass, radius=RANGE_GLOBAL, sort_dist=False)
        
        if self.death and Tags.Living in evt.unit.tags:
            self.owner.level.queue_spell(self.raise_skeleton(evt.unit))

        if self.salvation and Tags.Living in evt.unit.tags and random.random() < 1/6:
            prophet = Unit()
            prophet.asset = ["MissingSynergies", "Units", "cultist_prophet"]
            prophet.name = "Cultist Prophet"
            prophet.tags = [Tags.Holy, Tags.Dark]
            prophet.resists[Tags.Holy] = 100
            prophet.resists[Tags.Dark] = 100
            prophet.max_hp = self.spell.get_stat("minion_health")*2
            prophet.spells = [CultistProphetHeavenlyBlast(damage=self.spell.get_stat("minion_damage", base=8), range=self.spell.get_stat("minion_range", base=9))]
            prophet.buffs = [CultistProphetBuff(self.spell.get_stat("radius", base=4))]
            self.spell.summon(prophet, radius=RANGE_GLOBAL, sort_dist=False)

class CultOfDarknessBuff(Buff):

    def __init__(self, spell):
        self.spell = spell
        Buff.__init__(self)

    def on_init(self):
        self.name = "Cult of Darkness"
        self.asset = ["MissingSynergies", "Statuses", "cult_of_darkness"]
        self.color = Tags.Dark.color
        self.num_summons = self.spell.get_stat("num_summons")

    def get_description(self):
        passive = self.owner.get_buff(CultOfDarknessPassive)
        if not passive:
            return None
        return ("%i more cultist deaths needed to summon a dark tormenting mass." % (66 - passive.counter)) if passive.torment else None

    def on_advance(self):
        for _ in range(self.num_summons):
            unit = Cultist()
            apply_minion_bonuses(self.spell, unit)
            self.spell.summon(unit, radius=RANGE_GLOBAL, sort_dist=False)

class CultistProphetHeavenlyBlast(FalseProphetHolyBlast):

    def __init__(self, damage, range):
        FalseProphetHolyBlast.__init__(self)
        self.damage_type = Tags.Dark
        self.damage = damage
        self.range = range
        self.requires_los = False
        self.description += "\nIgnores walls"

    def get_ai_target(self):
        enemy = self.get_corner_target(self.get_stat("radius"))
        if enemy:
            return enemy
        else:
            allies = [u for u in self.caster.level.get_units_in_ball(self.caster, self.get_stat('range')) if u != self.caster and not are_hostile(self.caster, u) and not u.is_player_controlled]
            allies = [u for u in allies if u.cur_hp < u.max_hp]
            if allies:
                return random.choice(allies)
        return None

    def cast(self, x, y):
        target = Point(x, y)

        def deal_damage(point):
            unit = self.caster.level.get_unit_at(point.x, point.y)
            if unit and not are_hostile(unit, self.caster) and not unit is self.caster and not unit.is_player_controlled:
                unit.deal_damage(-self.get_stat('damage'), Tags.Heal, self)
            elif unit is self.caster:
                pass
            elif unit and unit.is_player_controlled and not are_hostile(self.caster, unit):
                pass
            else:
                self.caster.level.deal_damage(point.x, point.y, self.get_stat('damage'), self.damage_type, self)

        points_hit = set()
        for point in Bolt(self.caster.level, self.caster, target, find_clear=False):
            deal_damage(point)
            points_hit.add(point)
            yield

        stagenum = 0
        for stage in Burst(self.caster.level, target, self.get_stat('radius'), ignore_walls=True):
            for point in stage:
                if point in points_hit:
                    continue
                deal_damage(point)

            stagenum += 1
            for i in range(3):
                yield

class CultistProphetBuff(Buff):

    def __init__(self, radius):
        self.radius = radius
        Buff.__init__(self)

    def on_init(self):
        self.name = "Cult Prophecy"
        self.color = Tags.Dark.color
        self.description = "All dark damage done by this unit is redealt as holy damage.\n\nEach turn, enemies within %i tiles permanently lose 10 dark resistance.\n\nWhen this unit is about to die, sacrifice an allied living or undead cultist within %i tiles to fully heal self." % (self.radius, self.radius)
        self.global_triggers[EventOnPreDamaged] = self.on_pre_damaged
        self.owner_triggers[EventOnDamaged] = self.on_damaged
    
    def on_pre_damaged(self, evt):
        if evt.damage_type != Tags.Dark or not evt.source or evt.source.owner is not self.owner or not are_hostile(evt.unit, self.owner):
            return
        evt.unit.deal_damage(evt.damage, Tags.Holy, evt.source)
    
    def on_damaged(self, evt):
        if self.owner.cur_hp > 0:
            return
        units = [unit for unit in self.owner.level.get_units_in_ball(self.owner, self.radius) if unit.source is self.owner.source and (Tags.Living in unit.tags or Tags.Undead in unit.tags)]
        if not units:
            return
        unit = random.choice(units)
        unit.cur_hp = 0
        unit.kill()
        self.owner.cur_hp = 1
        self.owner.deal_damage(-self.owner.max_hp, Tags.Heal, self)
    
    def on_advance(self):
        for unit in [unit for unit in self.owner.level.get_units_in_ball(self.owner, self.radius) if are_hostile(unit, self.owner)]:
            unit.apply_buff(RevelationBuff())

    # For my No More Scams mod
    def can_redeal(self, target, source, dtype):
        if dtype != Tags.Dark or source.owner is not self.owner:
            return False
        return not is_immune(target, source, Tags.Holy)

class RevelationBuff(Buff):
    def on_init(self):
        self.name = "Revelation"
        self.buff_type = BUFF_TYPE_CURSE
        self.stack_type = STACK_INTENSITY
        self.color = Tags.Dark.color
        self.resists[Tags.Dark] = -10
        self.asset = ["MissingSynergies", "Statuses", "amplified_dark"]

class CultOfDarknessSpell(Spell):

    def on_init(self):
        self.name = "Cult of Darkness"
        self.asset = ["MissingSynergies", "Icons", "cult_of_darkness"]
        self.tags = [Tags.Dark, Tags.Conjuration, Tags.Enchantment]
        self.level = 3
        self.max_charges = 3
        self.duration = 16
        self.range = 0

        self.minion_health = 6
        self.minion_range = 6
        self.minion_damage = 1
        self.num_summons = 2
    
        self.upgrades["num_summons"] = (1, 3)
        self.upgrades["death"] = (1, 4, "Cult of Death", "Whenever an allied [living] cultist dies, raise it as a skeleton with double the HP.\nThese skeletons count as cultists for some of this spell's upgrades.")
        self.upgrades["salvation"] = (1, 4, "Cult of Salvation", "Whenever an allied [living] cultist dies, there is a 1/6 chance to summon a cultist prophet on a random tile.\nThe cultist prophet is a [holy] non-living unit with double the HP of a normal cultist, and its attack is much more powerful without self-damage.\nEach turn, enemies near the cultist prophet permanently lose [10_dark:dark] resistance.\nWhen the cultist prophet is about to die, a nearby allied [living] or [undead] cultist will be sacrificed to heal it to full HP.")
        self.upgrades["torment"] = (1, 3, "Cult of Torment", "For every 66 [living] or [undead] cultists that die, summon a dark tormenting mass on a random tile.")

    def get_description(self):
        return ("Each turn, summon [{num_summons}:num_summons] cultists on random tiles.\n"
                "A cultist has [{minion_health}_HP:minion_health], and an attack with [{minion_range}_range:minion_range] that ignores walls and deals [{minion_damage}_dark:dark] damage to the target and [1_physical:physical] damage to the cultist.\n"
                "Lasts [{duration}_turns:duration].").format(**self.fmt_dict())

    def cast_instant(self, x, y):
        passive = CultOfDarknessPassive(self)
        existing = self.caster.get_buff(CultOfDarknessPassive)
        if existing:
            passive.counter = existing.counter
        self.caster.apply_buff(passive)
        self.caster.apply_buff(CultOfDarknessBuff(self), self.get_stat("duration"))

class WoeBuff(Buff):
    def __init__(self, name, tag, amount):
        Buff.__init__(self)
        self.name = name
        self.resists[tag] = -amount
        self.buff_type = BUFF_TYPE_CURSE
        self.stack_type = STACK_REPLACE
        self.color = tag.color

class SpiritsOfWoeSpell(Spell):

    def __init__(self, spell):
        self.spell = spell
        Spell.__init__(self)
    
    def on_init(self):
        self.name = "Spirits of Woe"
        self.range = 0
        self.cool_down = self.spell.get_stat("summon_cooldown")
        self.description = "Summon the spirits of woe around the caster."
    
    def cast_instant(self, x, y):
        self.spell.summon_ghosts(self.caster)

class BoxOfWoeAura(Buff):

    def __init__(self, spell):
        self.spell = spell
        Buff.__init__(self)

    def on_init(self):
        self.name = "Aura of Woe"
        self.radius = self.spell.get_stat("radius")
        self.poison = self.spell.get_stat("poison")
        self.description = "Each turn, deal 1 dark, 1 lightning, %s damage to enemies in a %i tile radius." % ("1 ice, and 1 poison" if self.poison else "and 1 ice", self.radius)

    def on_advance(self):

        effects_left = 7
        dtypes = [Tags.Dark, Tags.Lightning, Tags.Ice]
        if self.poison:
            dtypes.append(Tags.Poison)

        for unit in self.owner.level.get_units_in_ball(Point(self.owner.x, self.owner.y), self.radius):
            if unit is self.owner:
                continue
            if not are_hostile(self.owner, unit):
                continue
            for dtype in dtypes:
                unit.deal_damage(1, dtype, self)
            effects_left -= 1

        # Show some graphical indication of this aura if it didnt hit much
        points = self.owner.level.get_points_in_ball(self.owner.x, self.owner.y, self.radius)
        points = [p for p in points if not self.owner.level.get_unit_at(p.x, p.y)]
        random.shuffle(points)
        for _ in range(effects_left):
            if not points:
                break
            p = points.pop()
            self.owner.level.show_effect(p.x, p.y, random.choice(dtypes), minor=True)

class WoeTeleportyBuff(Buff):

    def __init__(self, tag):
        self.tag = tag
        Buff.__init__(self)
        self.color = self.tag.color
        self.description = "Each turn, teleports closer toward the closest enemy resistant to %s before acting." % self.tag.name
    
    def on_pre_advance(self):
        units = [unit for unit in self.owner.level.units if are_hostile(unit, self.owner) and unit.resists[self.tag] > 0]
        if not units:
            return
        target = min(units, key=lambda unit: distance(unit, self.owner))
        points = [point for point in self.owner.level.get_points_in_ball(target.x, target.y, distance(target, self.owner)) if self.owner.level.can_move(self.owner, point.x, point.y, teleport=True)]
        if not points:
            return
        dest = random.choice(points)
        self.owner.level.show_effect(self.owner.x, self.owner.y, Tags.Translocation)
        self.owner.level.act_move(self.owner, dest.x, dest.y, teleport=True)

class WoeBlastSpell(SimpleRangedAttack):

    def __init__(self, tag, name, range, damage):
        SimpleRangedAttack.__init__(self, name=name, damage=damage, damage_type=tag, range=range)
        self.description = "Reduces %s resistance to 0 before dealing damage." % (self.damage_type.name)

    def can_redeal(self, target):
        return True

    def hit(self, x, y):
        unit = self.caster.level.get_unit_at(x, y)
        if unit and unit.resists[self.damage_type] > 0:
            unit.apply_buff(WoeBuff(self.name, self.damage_type, unit.resists[self.damage_type]))
        self.caster.level.deal_damage(x, y, self.get_stat("damage"), self.damage_type, self)
        
class BoxOfWoeSpell(Spell):

    def on_init(self):
        self.name = "Box of Woe"
        self.asset = ["MissingSynergies", "Icons", "box_of_woe"]
        self.tags = [Tags.Dark, Tags.Lightning, Tags.Ice, Tags.Conjuration]
        self.level = 5
        self.max_charges = 3
        self.range = 10
        self.requires_los = False
        self.must_target_empty = True
        self.must_target_walkable = True

        self.minion_health = 25
        self.minion_damage = 6
        self.minion_range = 4
        self.radius = 6
        self.summon_cooldown = 10

        self.upgrades["minion_health"] = (10, 3)
        self.upgrades["radius"] = (2, 4)
        self.upgrades["summon_cooldown"] = (-3, 3)
        self.upgrades["poison"] = (1, 4, "Repugnance", "Box of Woe will also summon Repugnance, a [poison] ghost.\nThe box's aura will also deal [poison] damage.")
        self.upgrades["chase"] = (1, 3, "Relentless Woe", "Each turn, before it acts, each ghost summoned by the Box of Woe is guaranteed to teleport closer to the closest enemy that resists its element.")

    def get_description(self):
        return ("Summon the Box of Woe, an immobile [construct] with [{minion_health}_HP:minion_health] that deals [1_dark:dark], [1_lightning:lightning], and [1_ice:ice] damage in a [{radius}_tile:radius] radius around itself each turn.\n"
                "Every [{summon_cooldown}_turns:duration], the box summons three ghosts, each corresponding to the elements of [dark], [lightning], and [ice]. Each ghost has an attack with [{minion_range}_range:minion_range] that permanently reduces the target's resistance to its element to 0.\n"
                "Casting this spell again while the box is already summoned will teleport it to the target tile and instantly summon its ghosts without triggering cooldown.").format(**self.fmt_dict())

    def cast_instant(self, x, y):

        existing = None
        for unit in self.caster.level.units:
            if unit.name == "Box of Woe" and unit.source is self:
                existing = unit
                break
        if existing:
            if self.caster.level.can_move(existing, x, y, teleport=True):
                self.caster.level.show_effect(existing.x, existing.y, Tags.Translocation)
                self.caster.level.act_move(existing, x, y, teleport=True)
            self.summon_ghosts(existing)
            return
        
        unit = Unit()
        unit.unique = True
        unit.name = "Box of Woe"
        unit.max_hp = self.get_stat("minion_health")
        unit.tags = [Tags.Dark, Tags.Lightning, Tags.Ice, Tags.Construct]
        for tag in [Tags.Dark, Tags.Lightning, Tags.Ice]:
            unit.resists[tag] = 100
        unit.stationary = True
        unit.spells = [SpiritsOfWoeSpell(self)]
        unit.buffs = [BoxOfWoeAura(self)]
        self.summon(unit, target=Point(x, y))

    def summon_ghosts(self, minion):

        tags = [Tags.Dark, Tags.Lightning, Tags.Ice]
        if self.get_stat("poison"):
            tags.append(Tags.Poison)
        
        chase = self.get_stat("chase")
        minion_health = self.get_stat("minion_health", base=4)
        minion_damage = self.get_stat("minion_damage")
        minion_range = self.get_stat("minion_range")

        for tag in tags:
            unit = Ghost()
            if tag == Tags.Dark:
                unit.name = "Death"
                unit.asset_name = "death_ghost"
            elif tag == Tags.Lightning:
                unit.name = "Pain"
                unit.asset_name = "pain_ghost"
            elif tag == Tags.Ice:
                unit.name = "Sorrow"
                unit.asset_name = "sorrow_ghost"
            else:
                unit.name = "Repugnance"
                unit.asset = ["MissingSynergies", "Units", "repugnance_ghost"]
            unit.max_hp = minion_health
            unit.resists[tag] = 100
            unit.tags = [Tags.Undead, tag]
            unit.spells = [WoeBlastSpell(tag, unit.name, minion_range, minion_damage)]
            if chase:
                unit.buffs.append(WoeTeleportyBuff(tag))
            self.summon(unit, target=minion, radius=5, sort_dist=False)

class PhaseInsanityBuff(Buff):

    def __init__(self, spell):
        self.spell = spell
        Buff.__init__(self)
    
    def on_init(self):
        self.name = "Phase Insanity"
        self.color = Tags.Arcane.color
        self.description = "25% chance on teleport and 100% chance on death to summon an insanity hound allied to the wizard."
        self.owner_triggers[EventOnMoved] = self.on_moved
        self.owner_triggers[EventOnDeath] = lambda evt: self.spell.summon(self.spell.get_hound(), target=self.owner, radius=5)
    
    def on_applied(self, owner):
        if are_hostile(self.owner, self.spell.caster):
            self.buff_type = BUFF_TYPE_CURSE
        else:
            self.buff_type = BUFF_TYPE_PASSIVE
        if self.spell.get_stat("distortion"):
            self.global_bonuses["range"] = -2 if self.buff_type == BUFF_TYPE_CURSE else 2
            self.global_bonuses["radius"] = -1 if self.buff_type == BUFF_TYPE_CURSE else 1
    
    def on_moved(self, evt):
        if not evt.teleport or random.random() >= 0.25:
            return
        self.spell.summon(self.spell.get_hound(), target=self.owner, radius=5)

class InvokeMadnessSpell(Spell):

    def __init__(self, spell):
        self.spell = spell
        Spell.__init__(self)
    
    def on_init(self):
        self.name = "Invoke Madness"
        self.range = 0
        self.radius = self.spell.get_stat("minion_range")
        self.cool_down = 3
        self.description = "Inflicts Phase Insanity on enemies and teleports them up to 5 tiles away."
    
    def get_targets(self):
        return [unit for unit in self.caster.level.get_units_in_ball(self.owner, self.get_stat("radius")) if are_hostile(self.caster, unit)]

    def can_cast(self, x, y):
        if not self.get_targets():
            return False
        return Spell.can_cast(self, x, y)
    
    def cast_instant(self, x, y):
        for unit in self.get_targets():
            unit.apply_buff(PhaseInsanityBuff(self.spell))
            randomly_teleport(unit, radius=5)

class MadWerewolfSpell(Spell):

    def on_init(self):
        self.name = "Mad Werewolf"
        self.asset = ["MissingSynergies", "Icons", "mad_werewolf"]
        self.tags = [Tags.Dark, Tags.Arcane, Tags.Nature, Tags.Conjuration]
        self.level = 3
        self.max_charges = 6
        self.requires_los = False
        self.must_target_empty = True
        self.must_target_walkable = True

        self.shields = 1
        self.minion_health = 18
        self.minion_range = 4
        self.minion_damage = 6

        self.upgrades["minion_range"] = (2, 3)
        self.upgrades["shields"] = (3, 3)
        self.upgrades["holy"] = (1, 2, "Lunacy", "Mad werewolves become [holy] units, and gain [150_holy:holy] and [100_poison:poison] resistance.")
        self.upgrades["distortion"] = (1, 4, "Phase Distortion", "Enemies afflicted with Phase Insanity suffer [-2_range:range] and [-1_radius:radius] on all spells.\nMad werewolves and wild men instead gain bonuses to these stats.")

    def get_description(self):
        return ("Summon a demonically possessed werewolf with [{minion_health}_HP:minion_health] and [{shields}_SH:shields]. It has a melee attack and teleport attack with [{minion_range}_range:minion_range] that deal [{minion_damage}_arcane:arcane] damage.\n"
                "The werewolf has Phase Insanity, and its melee attack inflicts Phase Insanity and teleports enemies away. Units with Phase Insanity have 25% chance on teleport and 100% chance on death to summon an insanity hound allied to the wizard.\n"
                "On reaching 0 HP, the werewolf transforms into a wild man that inflicts Phase Insanity on nearby enemies and teleports them away while fleeing, until it transforms into a werewolf again in [20_turns:duration].").format(**self.fmt_dict())

    def get_werewolf(self):

        unit = Unit()
        unit.name = "Mad Werewolf"
        unit.asset = ["MissingSynergies", "Units", "mad_werewolf"]
        unit.tags = [Tags.Living, Tags.Arcane, Tags.Nature, Tags.Dark]
        unit.resists[Tags.Arcane] = 100
        unit.resists[Tags.Dark] = 75
        unit.resists[Tags.Holy] = -50
        unit.max_hp = self.get_stat("minion_health")
        unit.shields = self.get_stat("shields")
        if self.get_stat("holy"):
            unit.tags.append(Tags.Holy)
            unit.resists[Tags.Holy] = 100
            unit.resists[Tags.Poison] = 100
        
        def onhit(caster, unit):
            unit.apply_buff(PhaseInsanityBuff(self))
            randomly_teleport(unit, radius=5)
        
        damage = self.get_stat("minion_damage")
        melee = SimpleMeleeAttack(damage=damage, damage_type=Tags.Arcane, onhit=onhit)
        melee.description = "Inflicts Phase Insanity on the target and teleports it up to 5 tiles away."
        leap = LeapAttack(damage=damage, range=self.get_stat("minion_range"), damage_type=Tags.Arcane, is_leap=False, is_ghost=True)
        leap.name = "Phase Pounce"
        unit.spells = [melee, leap]
        unit.buffs = [PhaseInsanityBuff(self), RespawnAs(self.get_wild_man)]

        return unit
    
    def get_wild_man(self):
        unit = Unit()
        unit.name = "Mad Wild Man"
        unit.asset = ["MissingSynergies", "Units", "mad_wild_man"]
        unit.tags = [Tags.Living, Tags.Arcane]
        unit.resists[Tags.Arcane] = 100
        unit.max_hp = self.get_stat("minion_health", base=8)
        unit.shields = self.get_stat("shields")
        unit.is_coward = True
        unit.spells = [InvokeMadnessSpell(self)]
        unit.buffs = [PhaseInsanityBuff(self), MatureInto(self.get_werewolf, 20)]
        return unit
    
    def get_hound(self):
        unit = InsanityHound()
        unit.max_hp = self.get_stat("minion_health", base=13)
        unit.shields = self.get_stat("shields")
        damage = self.get_stat("minion_damage")
        swap = VoidRip()
        swap.max_charges = 0
        swap.cur_charges = 0
        swap.cool_down = 3
        swap.requires_los = False
        swap.damage = damage
        swap.damage_type = Tags.Arcane
        swap.range = self.get_stat("minion_range")
        swap.description = "Ignores LOS. Swaps place with the target and deals damage."
        unit.spells[0] = swap
        unit.spells[1].damage = damage
        return unit

    def cast_instant(self, x, y):
        self.summon(self.get_werewolf(), target=Point(x, y))

class ParlorTrickDummySpell(Spell):
    def __init__(self, tag):
        Spell.__init__(self)
        self.tags = [tag]
        self.name = "%s Trick" % tag.name
        self.range = RANGE_GLOBAL
        self.requires_los = False
        self.can_target_self = True
        self.level = 1
    def cast_instant(self, x, y):
        return

class ParlorTrickEndless(Upgrade):

    def on_init(self):
        self.name = "Endless Trick"
        self.level = 4
        self.description = "Each cast of Parlor Trick has a 75% chance to cast itself again, as long as it has enough charges.\nThis upgrade cannot copy Parlor Trick more times in a turn than the spell has max charges."
        self.spell_bonuses[ParlorTrickSpell]["endless"] = 1
    
    def on_applied(self, owner):
        self.prereq.times_copied = 0

    def on_pre_advance(self):
        self.prereq.times_copied = 0

class ParlorTrickSpell(Spell):

    def on_init(self):
        self.name = "Parlor Trick"
        self.asset = ["MissingSynergies", "Icons", "parlor_trick"]
        self.tags = [Tags.Chaos, Tags.Sorcery]
        self.level = 1
        self.max_charges = 20
        self.range = 12
        self.times_copied = 0

        self.upgrades["requires_los"] = (-1, 2, "Blindcasting", "Parlor Trick can be cast without line of sight.")
        self.upgrades["max_charges"] = (15, 2)
        self.upgrades["range"] = (5, 2)
        self.add_upgrade(ParlorTrickEndless())

    def get_description(self):
        return ("Pretend to cast a [fire] spell, an [ice] spell, a [lightning] spell, a [nature] spell, an [arcane] spell, a [holy] spell, and a [dark] spell at the target tile in random order, triggering all effects that are normally triggered when casting spells with those tags.\n"
                "These fake spells are considered level 1 and have no other tags.").format(**self.fmt_dict())

    def cast(self, x, y):
        
        for point in Bolt(self.caster.level, self.caster, Point(x, y), find_clear=False):
            self.caster.level.show_effect(point.x, point.y, random.choice([Tags.Fire, Tags.Ice, Tags.Lightning, Tags.Poison, Tags.Holy, Tags.Dark, Tags.Arcane, Tags.Physical]), minor=random.choice([True, False]))
            yield
        
        tags = [Tags.Fire, Tags.Ice, Tags.Lightning, Tags.Nature, Tags.Holy, Tags.Dark, Tags.Arcane]
        random.shuffle(tags)
        for tag in tags:
            spell = ParlorTrickDummySpell(tag)
            spell.caster = self.caster
            spell.owner = self.caster
            self.caster.level.event_manager.raise_event(EventOnSpellCast(spell, self.caster, x, y), self.caster)
        
        if self.get_stat("endless") and self.can_cast(x, y) and self.cur_charges > 0 and self.times_copied < self.get_stat("max_charges") and random.random() < 0.75:
            self.times_copied += 1
            self.caster.level.act_cast(self.caster, self, x, y)

class GrudgeReaperBuff(Soulbound):

    def __init__(self, spell, target):
        self.relentless = spell.get_stat("relentless")
        self.insatiable = spell.get_stat("insatiable")
        self.spell = spell
        Soulbound.__init__(self, target)
        self.color = Tags.Demon.color
    
    def on_init(self):
        Soulbound.on_init(self)
        self.description = "Cannot be killed when the target of its grudge is alive. Vanishes when the target dies."
        self.global_triggers[EventOnDeath] = self.on_death

    def on_death(self, evt):
        if evt.unit is not self.guardian:
            return
        if self.insatiable and Point(evt.unit.x, evt.unit.y) not in self.owner.level.get_adjacent_points(Point(self.owner.x, self.owner.y), filter_walkable=False):
            units = [unit for unit in self.owner.level.units if are_hostile(unit, self.spell.caster)]
            if units:
                self.guardian = random.choice(units)
                return
        self.owner.cur_hp = 0
        self.owner.kill(trigger_death_event=False)

    def on_pre_advance(self):
        if not self.guardian.is_alive():
            self.owner.cur_hp = 0
            self.owner.kill(trigger_death_event=False)
        if not self.relentless:
            return
        target = self.guardian
        points = [point for point in self.owner.level.get_points_in_ball(target.x, target.y, distance(target, self.owner)) if self.owner.level.can_move(self.owner, point.x, point.y, teleport=True)]
        if not points:
            return
        dest = random.choice(points)
        self.owner.level.show_effect(self.owner.x, self.owner.y, Tags.Translocation)
        self.owner.level.act_move(self.owner, dest.x, dest.y, teleport=True)

class HatredBuff(Buff):
    def on_init(self):
        self.name = "Hatred"
        self.buff_type = BUFF_TYPE_CURSE
        self.stack_type = STACK_INTENSITY
        self.color = Tags.Demon.color
        self.resists[Tags.Dark] = -100

class GrudgeReapSpell(SimpleMeleeAttack):

    def __init__(self, damage, grudge, hatred=False, shield_reap=False):
        self.grudge = grudge
        self.hatred = hatred
        self.shield_reap = shield_reap
        SimpleMeleeAttack.__init__(self, damage=damage, damage_type=Tags.Dark)
        self.name = "Grudge Reap"
        self.description = "Can only be used against the target of the user's grudge."
    
    def cast_instant(self, x, y):
        unit = self.caster.level.get_unit_at(x, y)
        if unit:
            if self.hatred:
                unit.apply_buff(HatredBuff())
            if self.shield_reap:
                unit.shields = max(0, unit.shields - 6)
        self.caster.level.deal_damage(x, y, self.get_stat("damage"), Tags.Dark, self)

    def can_cast(self, x, y):
        if x != self.grudge.guardian.x or y != self.grudge.guardian.y:
            return False
        return Spell.can_cast(self, x, y)

    # For my No More Scams mod
    def can_redeal(self, target):
        return self.hatred

class GrudgeReaperSpell(Spell):

    def on_init(self):
        self.name = "Grudge Reaper"
        self.asset = ["MissingSynergies", "Icons", "grudge_reaper"]
        self.tags = [Tags.Dark, Tags.Conjuration]
        self.level = 3
        self.max_charges = 10
        self.range = RANGE_GLOBAL
        self.requires_los = False
        self.can_target_empty = False

        self.minion_damage = 200
        self.minion_health = 31

        self.upgrades["max_charges"] = (5, 3)
        self.upgrades["relentless"] = (1, 3, "Relentless Grudge", "Each turn, before it acts, the reaper is guaranteed to teleport closer to the target of its grudge.")
        self.upgrades["shield_reap"] = (1, 2, "Shield Reaper", "The reaper's attack will remove up to [6_SH:shields] before dealing damage.")
        self.upgrades["hatred"] = (1, 5, "Overwhelming Hatred", "The reaper's attack will permanently reduce the target's [dark] resistance by 100 before dealing damage.\nThis reduction stacks.")
        self.upgrades["insatiable"] = (1, 4, "Insatiable Grudge", "If the target of the reaper's grudge dies while not adjacent to the reaper, the reaper will redirect its grudge toward another random enemy instead of vanishing.")

    def get_description(self):
        return ("Summon a demonic spirit next to yourself that bears a grudge against the target unit. It cannot be killed by damage while the target is alive, but vanishes without counting as dying when the target dies.\n"
                "The reaper has a melee attack that deals [{minion_damage}_dark:dark] damage, which can only be used against the target of its grudge.").format(**self.fmt_dict())

    def cast_instant(self, x, y):

        target = self.caster.level.get_unit_at(x, y)
        if not target:
            return
        
        def can_harm(unit, other):
            buff = unit.get_buff(GrudgeReaperBuff)
            if not buff:
                return False
            if other is not buff.guardian:
                return False
            return Unit.can_harm(unit, other)
        
        unit = Reaper()
        unit.name = "Grudge Reaper"
        unit.asset = ["MissingSynergies", "Units", "grudge_reaper"]
        unit.tags.append(Tags.Demon)
        unit.resists[Tags.Poison] = 100
        unit.max_hp = self.get_stat("minion_health")
        buff = GrudgeReaperBuff(self, target)
        unit.buffs = [buff]
        unit.spells = [GrudgeReapSpell(self.get_stat("minion_damage"), buff, self.get_stat("hatred"), self.get_stat("shield_reap"))]
        unit.can_harm = lambda other: can_harm(unit, other)
        self.summon(unit, radius=5)

class BlackWail(BreathWeapon):

    def __init__(self, damage, range):
        BreathWeapon.__init__(self)
        self.damage_type = Tags.Dark
        self.damage = damage
        self.range = range
        self.name = "Black Wail"
        self.description = "Deals damage to enemies in a cone."
        self.cool_down = 2
    
    def per_square_effect(self, x, y):
        unit = self.caster.level.get_unit_at(x, y)
        if not unit or not are_hostile(unit, self.caster):
            self.caster.level.show_effect(x, y, Tags.Dark)
        else:
            unit.deal_damage(self.get_stat("damage"), Tags.Dark, self)

class DeathMetalSpell(Spell):

    def on_init(self):
        self.name = "Death Metal"
        self.asset = ["MissingSynergies", "Icons", "death_metal"]
        self.tags = [Tags.Metallic, Tags.Dark, Tags.Conjuration]
        self.level = 6
        self.max_charges = 3
        self.range = 0

        self.minion_health = 78
        self.minion_damage = 13
        self.minion_range = 7
        self.minion_duration = 3
        self.num_summons = 4

        self.upgrades["num_summons"] = (2, 3, "Num Summons", "Up to [2:num_summons] more metalheads can be summoned.")
        self.upgrades["chorus"] = (1, 4, "Shrieking Chorus", "When you already have the normal maximum number of metalheads summoned, this spell has a chance to summon a metalhead beyond the maximum number each turn when channeled, equal to 100% divided by your current number of metalheads.")
        self.upgrades["gore"] = (1, 5, "Goregrind", "Each turn when channeling this spell, all of your minions gain a stack of bloodlust for a duration equal to this spell's [minion_duration:minion_duration], increasing all of their damage by 1.\nThe remaining durations of all of their bloodlust stacks are then increased by [1_turn:duration].")
        self.upgrades["discord"] = (1, 6, "Discordian Tune", "Each turn, each enemy has a 25% chance to take [1_dark:dark] or [1_physical:physical] damage.\nEnemies that take [physical] damage are [stunned] for [1_turn:duration].\nEnemies that take [dark] damage go [berserk] for [1_turn:duration].\nThese durations are fixed and unaffected by bonuses.")

    def get_description(self):
        return ("Channel this spell to create aggressive otherworldly music each turn to summon a metalhead near you and increase the remaining durations of all metalheads by [1_turn:minion_duration].\n"
                "Metalheads are stationary flying [metallic] [undead] minions with [{minion_health}_HP:minion_health] that last [{minion_duration}_turns:minion_duration]. They have wailing attack that deal [{minion_damage}_dark:dark] damage to enemies in a [{minion_range}_tile:minion_range] cone, and headbanging leap attacks that deal [{minion_damage}_physical:physical] with double the range.\n"
                "At most [{num_summons}:num_summons] metalheads can be summoned.\n").format(**self.fmt_dict())

    def cast(self, x, y, channel_cast=False):

        if not channel_cast:
            self.caster.apply_buff(ChannelBuff(self.cast, Point(x, y)))
            return

        minion_duration = self.get_stat("minion_duration")
        existing_num = len([unit for unit in self.caster.level.units if unit.source is self])
        if existing_num < self.get_stat("num_summons") or (self.get_stat("chorus") and random.random() < 1/existing_num):
            unit = GiantSkull()
            unit.name = "Metalhead"
            unit.asset = ["MissingSynergies", "Units", "metalhead"]
            unit.tags.append(Tags.Metallic)
            unit.resists[Tags.Ice] = 100
            unit.max_hp = self.get_stat("minion_health")
            minion_range = self.get_stat("minion_range")
            minion_damage = self.get_stat("minion_damage")
            leap = LeapAttack(damage=minion_damage, range=2*minion_range)
            leap.name = "Headbang"
            leap.cool_down = 2
            unit.spells = [leap, BlackWail(minion_damage, minion_range)]
            unit.turns_to_death = minion_duration
            self.summon(unit, radius=5, sort_dist=False)
        
        discord = self.get_stat("discord")
        gore = self.get_stat("gore")

        for unit in list(self.caster.level.units):

            if are_hostile(unit, self.caster):
                if not discord or random.random() >= 0.25:
                    continue
                if random.choice([True, False]):
                    dealt = unit.deal_damage(1, Tags.Dark, self)
                    if dealt:
                        unit.apply_buff(BerserkBuff(), 1)
                else:
                    dealt = unit.deal_damage(1, Tags.Physical, self)
                    if dealt:
                        unit.apply_buff(Stun(), 1)

            else:
                if unit.is_player_controlled:
                    continue
                if unit.source is self:
                    unit.turns_to_death += 1
                if gore:
                    unit.apply_buff(BloodrageBuff(1), minion_duration)
                    for buff in unit.buffs:
                        if isinstance(buff, BloodrageBuff) and buff.turns_left:
                            buff.turns_left += 1

        yield

class MutantCyclopsMassTelekinesis(Spell):

    def __init__(self, spell):
        self.spell = spell
        Spell.__init__(self)
    
    def on_init(self):
        self.name = "Mass Telekinesis"
        self.damage_type = Tags.Physical
        self.damage = self.spell.get_stat("minion_damage")
        self.range = self.spell.get_stat("minion_range")
        self.radius = self.spell.get_stat("radius")
        self.cool_down = 3
        self.num_targets = self.spell.get_stat("num_targets")
        self.requires_los = not self.spell.get_stat("phase")
        self.conjure = self.spell.get_stat("conjure")
    
    def get_description(self):
        return "Throw %i units toward the target, dealing damage and stunning in a radius based on the thrown unit's max HP." % self.get_stat("num_targets")
    
    def throw(self, x, y, unit):
        damage = self.get_stat("damage")
        phase = not self.get_stat("requires_los")
        if unit:
            if (unit.x != x or unit.y != y):
                old = Point(unit.x, unit.y)
                unit.invisible = True
                self.caster.level.act_move(unit, x, y, teleport=True)
                for point in self.caster.level.get_points_in_line(old, Point(x, y), find_clear=not phase):
                    self.caster.level.leap_effect(point.x, point.y, Tags.Physical.color, unit)
                    yield
                unit.invisible = False
        else:
            for point in Bolt(self.caster.level, self.caster, Point(x, y), find_clear=not phase):
                self.caster.level.show_effect(point.x, point.y, Tags.Physical, minor=True)
                yield
        
        for stage in Burst(self.caster.level, Point(x, y), math.ceil(unit.max_hp/40) if unit else 1, ignore_walls=phase):
            for point in stage:
                target = self.caster.level.get_unit_at(point.x, point.y)
                if not target or not are_hostile(target, self.caster):
                    self.caster.level.show_effect(point.x, point.y, Tags.Physical)
                else:
                    target.deal_damage(damage, Tags.Physical, self)
                    target.apply_buff(Stun(), 1)
            yield

    def get_thrown_units(self):
        units = [unit for unit in self.caster.level.get_units_in_ball(self.caster, self.get_stat("radius")) if (not (are_hostile(unit, self.caster)) or self.caster.max_hp > unit.max_hp) and not unit.is_player_controlled and unit is not self.caster]
        if self.get_stat("requires_los"):
            units = [unit for unit in units if self.caster.level.can_see(unit.x, unit.y, self.caster.x, self.caster.y)]
        return units

    def get_throw_target(self, x, y, unit):
        points = [point for point in self.caster.level.get_points_in_ball(x, y, self.get_stat("radius")) if self.caster.level.can_move(unit, point.x, point.y, teleport=True) or Point(unit.x, unit.y) == point]
        if self.get_stat("requires_los"):
            points = [point for point in points if self.caster.level.can_see(unit.x, unit.y, point.x, point.y)]
        if not points:
            return None
        return min(points, key=lambda point: distance(point, Point(x, y)))

    def can_cast(self, x, y):
        if not Spell.can_cast(self, x, y):
            return False
        if not self.conjure:
            units = self.get_thrown_units()
            if not units or all([not self.get_throw_target(x, y, unit) for unit in units]):
                return False
        return True

    def cast(self, x, y):
        units = self.get_thrown_units()
        random.shuffle(units)
        yield from self.throw_units(x, y, units, 0)

    def throw_units(self, x, y, units, num_thrown):

        num_targets = self.get_stat("num_targets")
        if num_thrown >= num_targets:
            return
        if not units:
            if num_thrown < num_targets and self.conjure:
                for _ in range(num_targets - num_thrown):
                    self.caster.level.queue_spell(self.throw(x, y, None))
            return
        
        target = self.get_throw_target(x, y, units[0])
        if target:
            yield from self.throw(target.x, target.y, units[0])
            num_thrown += 1
        units.pop(0)
        self.caster.level.queue_spell(self.throw_units(x, y, units, num_thrown))

class MutantCyclopsSpell(Spell):

    def on_init(self):
        self.name = "Mutant Cyclops"
        self.asset = ["MissingSynergies", "Icons", "mutant_cyclops"]
        self.tags = [Tags.Arcane, Tags.Conjuration]
        self.level = 6
        self.max_charges = 3
        self.range = 10
        self.requires_los = False
        self.must_target_empty = True
        self.must_target_walkable = True

        self.minion_health = 126
        self.minion_range = 15
        self.minion_damage = 13
        self.radius = 5
        self.num_targets = 4

        self.upgrades["minion_health"] = (84, 3)
        self.upgrades["num_targets"] = (2, 3, "Num Targets", "The mutant cyclops can throw [2:num_targets] more units at once.")
        self.upgrades["phase"] = (1, 6, "Phase Throw", "The mutant cyclops can now throw units not in its line of sight, at tiles not in each thrown unit's line of sight, passing through walls; each landing impact ignores walls.\nThe cyclops's leap attack becomes a teleport attack.")
        self.upgrades["conjure"] = (1, 3, "Conjure Rocks", "If there are fewer than the maximum number of throwable units in range, the mutant cyclops will make up for the difference by throwing rocks at the target.\nEach rock deals damage and stuns in a [1_tile:radius] radius.")
    
    def get_description(self):
        return ("Summon a mutant cyclops with [{minion_health}_HP:minion_health].\n It has a mass telekinesis ability with a [3_turn:duration] cooldown, which throws [{num_targets}:num_targets] units in LOS within [{radius}_tiles:radius] of itself toward an enemy [{minion_range}_tiles:minion_range] away. Upon landing, each unit deals [{minion_damage}_physical:physical] damage to all enemies in a burst with radius equal to the unit's max HP divided by 40, rounded up, and [stuns] for [1_turn:duration]. The wizard and enemies with more max HP than the cyclops cannot be thrown.\n"
                "The cyclops also has a leap attack with the same range and damage.\n"
                "Casting this spell again when the cyclops is already summoned will teleport it to the target tile and fully heal it.").format(**self.fmt_dict())

    def cast_instant(self, x, y):

        existing = None
        for unit in self.caster.level.units:
            if unit.source is self:
                existing = unit
                break
        if existing:
            self.caster.level.show_effect(existing.x, existing.y, Tags.Translocation)
            self.caster.level.act_move(existing, x, y, teleport=True)
            existing.deal_damage(-existing.max_hp, Tags.Heal, self)
            return
        
        unit = Unit()
        unit.unique = True
        unit.name = "Mutant Cyclops"
        unit.asset = ["MissingSynergies", "Units", "mutant_cyclops"]
        unit.tags = [Tags.Living, Tags.Arcane]
        unit.resists[Tags.Arcane] = 50
        unit.max_hp = self.get_stat("minion_health")
        minion_damage = self.get_stat("minion_damage")
        minion_range = self.get_stat("minion_range")
        phase = self.get_stat("phase")
        leap = LeapAttack(damage=minion_damage, range=minion_range, is_leap=not phase, is_ghost=phase)
        leap.name = "Telekinetic Leap"
        unit.spells = [MutantCyclopsMassTelekinesis(self), leap, SimpleMeleeAttack(damage=self.get_stat("minion_damage"))]
        self.summon(unit, target=Point(x, y))

class WastingBuff(Buff):

    def __init__(self, source):
        self.source = source
        Buff.__init__(self)
        self.name = "Wasting"

    def on_applied(self, owner):
        self.asset = ["MissingSynergies", "Statuses", "wasting"]
        self.color = Tags.Dark.color
        self.buff_type = BUFF_TYPE_CURSE
        self.max_hp = self.owner.max_hp
    
    def on_advance(self):
        if self.owner.max_hp < self.max_hp:
            self.owner.deal_damage(self.max_hp - self.owner.max_hp, Tags.Dark, self.source)

class PrimordialRotBuff(Buff):

    def __init__(self, spell):
        self.spell = spell
        Buff.__init__(self)
    
    def on_init(self):
        self.name = "Primordial Rot"
        self.color = Tags.Dark.color
        self.max_hp_steal = self.spell.get_stat("max_hp_steal")
        self.wasting = self.spell.get_stat("wasting")
        self.description = "Attacks steal %i max HP and deal bonus damage based on max HP.\n\nSplits into two copies with half HP on death if max HP is at least 8." % self.max_hp_steal
        self.global_triggers[EventOnPreDamaged] = self.on_pre_damaged
        self.owner_triggers[EventOnDeath] = self.on_death
    
    def on_pre_damaged(self, evt):
        if evt.damage <= 0 or evt.source.owner is not self.owner or not isinstance(evt.source, Spell):
            return
        # Queue this so the max HP drain happens after the triggering damage
        self.owner.level.queue_spell(self.effect(evt))
    
    def effect(self, evt):
        if self.wasting:
            evt.unit.apply_buff(WastingBuff(self))
        amount = min(evt.unit.max_hp, self.max_hp_steal)
        drain_max_hp_kill(evt.unit, self.max_hp_steal)
        self.owner.max_hp += amount
        self.owner.deal_damage(-amount, Tags.Heal, self)
        if evt.source.melee:
            damage = self.owner.max_hp//4
        else:
            damage = self.owner.max_hp//10
        evt.unit.deal_damage(damage, evt.damage_type, self)
        yield

    def on_advance(self):
        self.spell.update_sprite(self.owner)

    def on_death(self, evt):
        if self.owner.max_hp < 8:
            return
        for _ in range(2):
            self.spell.summon(self.spell.get_unit(self.owner.max_hp//2), target=self.owner, radius=5)

    # For my No More Scams mod
    def can_redeal(self, target, source, damage_type):
        return True

class PrimordialRotSpell(Spell):

    def on_init(self):
        self.name = "Primordial Rot"
        self.asset = ["MissingSynergies", "Icons", "primordial_rot"]
        self.tags = [Tags.Nature, Tags.Dark, Tags.Conjuration]
        self.level = 7
        self.max_charges = 2
        self.must_target_empty = True
        self.must_target_walkable = True

        self.minion_health = 64
        self.minion_damage = 3
        self.minion_duration = 10
        self.max_hp_steal = 4

        self.upgrades["minion_health"] = (64, 7)
        self.upgrades["minion_duration"] = (5, 3)
        self.upgrades["max_hp_steal"] = (4, 4)
        self.upgrades["wasting"] = (1, 4, "Primordial Wasting", "The slime's attacks permanently inflict primordial wasting, which deals [dark] damage each turn equal to the amount of max HP the target has lost since the debuff was inflicted.")

    def get_description(self):
        return ("Summon a [nature] [undead] [slime] minion for [{minion_duration}_turns:minion_duration]. It has [{minion_health}_HP:minion_health] and a melee attack that deals [{minion_damage}_dark:dark] damage.\n"
                "The slime's attacks steal [{max_hp_steal}:dark] max HP, and instantly kill targets with less max HP than that. Its melee attacks deal bonus damage equal to 25% of its max HP, and other attacks deal bonus damage equal to 10% of its max HP.\n"
                "On death, the slime splits into two slimes with half max HP if its max HP was at least 8.").format(**self.fmt_dict())

    def update_sprite(self, unit):
        if unit.max_hp >= 256:
            size = "huge"
        elif unit.max_hp >= 64:
            size = "large"
        elif unit.max_hp > 8:
            size = "medium"
        else:
            size = "small"
        new_asset = "primordial_rot_%s" % size
        if unit.asset[2] == new_asset:
            return
        unit.asset[2] = new_asset
        unit.Anim = None
    
    def get_unit(self, max_hp):
        unit = Unit()
        unit.name = "Primordial Rot"
        unit.max_hp = max_hp
        unit.asset = ["MissingSynergies", "Units", ""]
        self.update_sprite(unit)
        unit.tags = [Tags.Nature, Tags.Undead, Tags.Slime]
        unit.resists[Tags.Poison] = 100
        unit.resists[Tags.Physical] = 50
        unit.spells = [SimpleMeleeAttack(damage=self.get_stat("minion_damage"), damage_type=Tags.Dark)]
        unit.buffs = [PrimordialRotBuff(self)]
        unit.turns_to_death = self.get_stat("minion_duration")
        return unit
    
    def cast_instant(self, x, y):
        self.summon(self.get_unit(self.get_stat("minion_health")), target=Point(x, y))

class UnnaturalVitality(Upgrade):

    def on_init(self):
        self.name = "Unnatural Vitality"
        self.asset = ["MissingSynergies", "Icons", "unnatural_vitality"]
        self.tags = [Tags.Nature, Tags.Dark]
        self.level = 4
        self.description = "Your [living], [nature], and [demon] minions gain [-100_heal:heal] resistance, benefitting doubly from most sources of healing.\nThis will also counteract the healing suppression of the [poison] debuff."
        self.global_triggers[EventOnUnitAdded] = self.on_unit_added
    
    def on_unit_added(self, evt):
        if evt.unit.is_player_controlled or are_hostile(evt.unit, self.owner):
            return
        if not [tag for tag in [Tags.Living, Tags.Nature, Tags.Demon] if tag in evt.unit.tags]:
            return
        evt.unit.resists[Tags.Heal] -= 100

class CosmicStasisBuff(Buff):

    def __init__(self, spell):
        self.freeze_extension = spell.get_stat("freeze_extension")
        Buff.__init__(self)
        if spell.get_stat("laser"):
            self.global_triggers[EventOnDamaged] = self.on_damaged
    
    def on_init(self):
        self.name = "Cosmic Stasis"
        self.color = Tags.Ice.color
        self.global_triggers[EventOnBuffApply] = self.on_buff_apply
        self.global_triggers[EventOnBuffRemove] = self.on_buff_remove
        self.to_refreeze = []

    def on_buff_apply(self, evt):
        if isinstance(evt.buff, FrozenBuff) and are_hostile(evt.unit, self.owner) and not evt.unit.gets_clarity:
            evt.buff.turns_left += self.freeze_extension

    def on_buff_remove(self, evt):
        if not isinstance(evt.buff, FrozenBuff) or evt.buff.break_dtype != Tags.Physical:
            return
        if not are_hostile(evt.unit, self.owner) or not evt.unit.is_alive():
            return
        self.to_refreeze.append(evt.unit)

    def on_pre_advance(self):
        for unit in self.to_refreeze:
            unit.apply_buff(FrozenBuff(), 1)
        self.to_refreeze = []

    def on_damaged(self, evt):
        if evt.damage_type != Tags.Arcane or not are_hostile(evt.unit, self.owner):
            return
        if random.random() < evt.damage/100:
            evt.unit.apply_buff(FrozenBuff(), 1)

class CosmicStasisSpell(Spell):

    def on_init(self):
        self.name = "Cosmic Stasis"
        self.asset = ["MissingSynergies", "Icons", "cosmic_stasis"]
        self.tags = [Tags.Arcane, Tags.Ice, Tags.Enchantment]
        self.level = 5
        self.max_charges = 3
        self.range = 0
        self.duration = 5
        self.freeze_extension = 1

        self.upgrades["duration"] = (5, 3)
        self.upgrades["freeze_extension"] = (1, 3, "Freeze Extension", "When an enemy is [frozen], the duration of freeze is extended by [1:duration] more turn.")
        self.upgrades["laser"] = (1, 5, "Laser Cooling", "When an enemy takes [arcane] damage, it has a chance of being [frozen] for [1_turn:duration] equal to the damage taken divided by 100, to a maximum of 100%.")
    
    def get_description(self):
        return ("When an enemy is [frozen], the duration of freeze is extended by [{freeze_extension}_turns:duration]. Does not work on targets that can gain clarity.\n"
                "When an enemy is unfrozen by [physical] damage, that enemy will be [frozen] again before the start of your next turn.\n"
                "Lasts [{duration}_turns:duration].").format(**self.fmt_dict())

    def cast_instant(self, x, y):
        self.caster.apply_buff(CosmicStasisBuff(self), self.get_stat("duration"))

class OblivionBuff(Buff):
    def on_init(self):
        self.name = "Oblivion"
        self.asset = ["MissingSynergies", "Statuses", "amplified_dark"]
        self.buff_type = BUFF_TYPE_CURSE
        self.color = Tags.Dark.color
        self.resists[Tags.Dark] = -100

class WellOfOblivionSpell(Spell):

    def on_init(self):
        self.name = "Well of Oblivion"
        self.asset = ["MissingSynergies", "Icons", "well_of_oblivion"]
        self.tags = [Tags.Dark, Tags.Translocation, Tags.Sorcery]
        self.level = 5
        self.max_charges = 4
        self.range = 0
        self.radius = 6
        self.duration = 3

        self.upgrades["max_charges"] = (3, 2)
        self.upgrades["radius"] = (3, 3)
        self.upgrades["duration"] = (3, 3)
        self.upgrades["dust"] = (1, 5, "To Dust", "Walls in the affected radius are destroyed.")
        self.upgrades["encroach"] = (1, 5, "Encroaching Dark", "Affected enemies lose [100_dark:dark] resistance for the same duration.")

    def get_description(self):
        return ("All enemies in a [{radius}_tile:radius] radius are teleported as close to you as possible, and [stunned] for [{duration}_turns:duration].").format(**self.fmt_dict())

    def cast_instant(self, x, y):

        radius = self.get_stat("radius")
        encroach = self.get_stat("encroach")
        duration = self.get_stat("duration")
        
        if self.get_stat("dust"):
            for point in self.caster.level.get_points_in_ball(self.caster.x, self.caster.y, radius):
                if self.caster.level.tiles[point.x][point.y].is_wall():
                    self.caster.level.make_floor(point.x, point.y)
        
        units = [unit for unit in self.caster.level.get_units_in_ball(self.caster, radius) if are_hostile(self.caster, unit)]
        random.shuffle(units)
        for unit in units:
            points = [point for point in self.caster.level.get_points_in_ball(self.caster.x, self.caster.y, radius) if self.caster.level.can_move(unit, point.x, point.y, teleport=True)]
            if not points:
                continue
            self.caster.level.show_effect(unit.x, unit.y, Tags.Translocation)
            target = min(points, key=lambda point: distance(point, self.caster))
            self.caster.level.act_move(unit, target.x, target.y, teleport=True)
            unit.apply_buff(Stun(), duration)
            if encroach:
                unit.apply_buff(OblivionBuff(), duration)

class ShockTroops(Upgrade):

    def on_init(self):
        self.name = "Shock Troops"
        self.asset = ["MissingSynergies", "Icons", "shock_troops"]
        self.tags = [Tags.Fire, Tags.Lightning]
        self.level = 5
        self.num_targets = 2
        self.radius = 1
        self.range = 6
        self.global_triggers[EventOnUnitAdded] = self.on_unit_added

    def get_description(self):
        return ("Whenever you summon a minion, it launches bombs at [{num_targets}:num_targets] targetable enemies in line of sight.\n"
                "Each bomb has a range of [{range}_tiles:range], and deals [fire] or [lightning] damage to enemies in a [{radius}_tile:radius] burst equal to 25% of the minion's max HP.").format(**self.fmt_dict())

    def boom(self, target, radius, damage):
        for stage in Burst(self.owner.level, target, radius):
            for point in stage:
                unit = self.owner.level.get_unit_at(point.x, point.y)
                if not unit or not are_hostile(unit, self.owner):
                    self.owner.level.show_effect(point.x, point.y, random.choice([Tags.Fire, Tags.Lightning]))
                else:
                    unit.deal_damage(damage, random.choice([Tags.Fire, Tags.Lightning]), self)
            yield

    def on_unit_added(self, evt):

        if evt.unit.is_player_controlled or are_hostile(evt.unit, self.owner):
            return

        targets = self.owner.level.get_units_in_ball(evt.unit, self.get_stat("range"))
        targets = [target for target in targets if are_hostile(self.owner, target) and self.owner.level.can_see(evt.unit.x, evt.unit.y, target.x, target.y)]
        if not targets:
            return
        targets = [Point(target.x, target.y) for target in targets]
        random.shuffle(targets)
        
        radius = self.get_stat("radius")
        damage = evt.unit.max_hp//4
        self.owner.level.queue_spell(send_bolts(lambda point: self.owner.level.show_effect(point.x, point.y, random.choice([Tags.Fire, Tags.Lightning]), minor=True), lambda point: self.owner.level.queue_spell(self.boom(point, radius, damage)), evt.unit, targets[:self.get_stat("num_targets")]))

class OverloadedBuff(Buff):

    def __init__(self, tag, amount):
        self.tag = tag
        Buff.__init__(self)
        self.resists[tag] = amount
    
    def on_init(self):
        self.name = "%s Overloaded" % self.tag.name
        if self.tag in [Tags.Fire, Tags.Ice, Tags.Lightning, Tags.Poison, Tags.Arcane, Tags.Physical, Tags.Holy, Tags.Dark]:
            self.asset = ["MissingSynergies", "Statuses", "amplified_%s" % self.tag.name.lower()]
        self.buff_type = BUFF_TYPE_CURSE
        self.stack_type = STACK_INTENSITY
        self.color = self.tag.color
    
    def on_attempt_apply(self, owner):
        existing = None
        for buff in owner.buffs:
            if isinstance(buff, OverloadedBuff) and buff.tag == self.tag:
                existing = buff
                break
        if existing:
            self.turns_left = max(existing.turns_left, self.turns_left)
            self.resists[self.tag] = min(self.resists[self.tag], existing.resists[self.tag])
            owner.remove_buff(existing)
        return True

class AegisOverloadSpell(Spell):

    def on_init(self):
        self.name = "Aegis Overload"
        self.asset = ["MissingSynergies", "Icons", "aegis_overload"]
        self.tags = [Tags.Metallic, Tags.Chaos, Tags.Sorcery]
        self.level = 4
        self.max_charges = 6
        self.range = 0
        self.radius = 6
        self.duration = 3

        self.upgrades["max_charges"] = (3, 2)
        self.upgrades["radius"] = (4, 2, "Radius", "Aegis Overload searches for enemy targets in a greater radius around each minion.")
        self.upgrades["phase"] = (1, 3, "Phase Overload", "The bolts sent out by Aegis Overload can now pass through walls.")
        self.upgrades["disrupt"] = (1, 5, "Disruptive Overload", "An enemy hit by a bolt from this spell will be inflicted with an overloaded debuff of the same element and magnitude as the one inflicted onto the minion who shot out that bolt.\nThis lasts [3_turns:duration] by default but benefits from this spell's bonuses to [duration].\nDamage dealt by this spell cannot benefit from the resistance reduction of overloaded debuffs on the target.")

    def get_description(self):
        return ("Each of your minions shoots out a bolt of energy for each of its resistances that is over 100.\n"
                "Each bolt targets a random enemy in line of sight within [{radius}_tiles:radius], and deals damage of the same element as the resistance that created the bolt, equal to the minion's max HP multiplied by the percentage of the resistance that is over 100.\n"
                "For each bolt the minion sent out, it is inflicted with an overloaded debuff of that element for [3_turns:duration], which reduces its resistance to that element to 100.").format(**self.fmt_dict())

    def get_impacted_tiles(self, x, y):
        eligible = []
        for unit in self.caster.level.units:
            if unit.is_player_controlled or are_hostile(unit, self.caster):
                continue
            for tag in unit.resists.keys():
                if unit.resists[tag] > 100:
                    eligible.append(unit)
                    break
        return [Point(unit.x, unit.y) for unit in eligible]

    def bolt(self, unit, tag, target, resist, damage, disrupt, duration):

        for point in Bolt(self.caster.level, unit, target, find_clear=False):
            self.caster.level.show_effect(point.x, point.y, tag, minor=True)
            yield
        
        existing = 0
        for buff in target.buffs:
            if isinstance(buff, OverloadedBuff) and buff.tag == tag:
                existing = buff.resists[tag]
                break
        target.resists[tag] -= existing
        target.deal_damage(damage, tag, self)
        target.resists[tag] += existing

        unit.apply_buff(OverloadedBuff(tag, -resist), 3)
        if disrupt:
            target.apply_buff(OverloadedBuff(tag, -resist), duration)

    def cast_instant(self, x, y):

        radius = self.get_stat("radius")
        phase = self.get_stat("phase")
        disrupt = self.get_stat("disrupt")
        duration = self.get_stat("duration")

        units = [unit for unit in self.caster.level.units if not unit.is_player_controlled and not are_hostile(unit, self.caster)]
        if not units:
            return
        random.shuffle(units)

        for unit in units:
            tags = []
            for tag in unit.resists.keys():
                if unit.resists[tag] <= 100:
                    continue
                tags.append(tag)
            if not tags:
                continue
            for tag in tags:
                targets = [target for target in self.caster.level.get_units_in_ball(unit, radius) if are_hostile(unit, target)]
                if not phase:
                    targets = [target for target in targets if self.caster.level.can_see(unit.x, unit.y, target.x, target.y)]
                if not targets:
                    break
                resist = unit.resists[tag] - 100
                damage = math.ceil(unit.max_hp*resist/100)
                self.caster.level.queue_spell(self.bolt(unit, tag, random.choice(targets), resist, damage, disrupt, duration))

class ChaosTrickDummySpell(Spell):
    def __init__(self, tag, level):
        Spell.__init__(self)
        self.tags = [tag]
        self.name = "%s Trick" % tag.name
        self.range = RANGE_GLOBAL
        self.requires_los = False
        self.can_target_self = True
        self.level = level
    def cast_instant(self, x, y):
        return

class ChaosTrick(Upgrade):

    def on_init(self):
        self.name = "Chaos Trick"
        self.asset = ["MissingSynergies", "Icons", "chaos_trick"]
        self.tags = [Tags.Fire, Tags.Lightning, Tags.Chaos]
        self.level = 4
        self.description = "Whenever you cast a [fire] spell, you pretend to cast a [lightning] spell and a [chaos] spell of the same level.\nWhenever you cast a [lightning] spell, you pretend to cast a [fire] spell and a [chaos] spell of the same level.\nWhenever you cast a [chaos] spell, you pretend to cast a [fire] spell and a [lightning] spell of the same level.\nThese fake spells trigger all effects that are normally triggered when casting spells with their tags, and have no other tags.\nThis skill cannot trigger itself."
        self.owner_triggers[EventOnSpellCast] = self.on_spell_cast
    
    def cast_dummy_spells(self, evt, tags):
        random.shuffle(tags)
        for tag in tags:
            spell = ChaosTrickDummySpell(tag, evt.spell.level)
            spell.caster = self.owner
            spell.owner = self.owner
            self.owner.level.event_manager.raise_event(EventOnSpellCast(spell, self.owner, evt.x, evt.y), self.owner)

    def on_spell_cast(self, evt):
        if isinstance(evt.spell, ChaosTrickDummySpell):
            return
        if Tags.Fire in evt.spell.tags:
            self.cast_dummy_spells(evt, [Tags.Lightning, Tags.Chaos])
        if Tags.Lightning in evt.spell.tags:
            self.cast_dummy_spells(evt, [Tags.Fire, Tags.Chaos])
        if Tags.Chaos in evt.spell.tags:
            self.cast_dummy_spells(evt, [Tags.Fire, Tags.Lightning])

class HolySoulDregsBuff(Buff):

    def __init__(self, upgrade):
        self.upgrade = upgrade
        Buff.__init__(self)
    
    def on_init(self):
        self.name = "Soul Dregs"
        self.color = Tags.Holy.color
        self.stack_type = STACK_DURATION
    
    def on_applied(self, owner):

        existing = owner.get_buff(DarkSoulDregsBuff)
        if not existing:
            return
        
        if existing.turns_left < self.turns_left:
            self.turns_left -= existing.turns_left
            owner.remove_buff(existing)
            self.upgrade.do_summon(existing.turns_left)
            return
        else:
            if existing.turns_left > self.turns_left:
                existing.turns_left -= self.turns_left
            else:
                owner.remove_buff(existing)
            self.upgrade.do_summon(self.turns_left)
            return ABORT_BUFF_APPLY

class DarkSoulDregsBuff(Buff):

    def __init__(self, upgrade):
        self.upgrade = upgrade
        Buff.__init__(self)
    
    def on_init(self):
        self.name = "Soul Dregs"
        self.color = Tags.Dark.color
        self.stack_type = STACK_DURATION
    
    def on_applied(self, owner):

        existing = owner.get_buff(HolySoulDregsBuff)
        if not existing:
            return
        
        if existing.turns_left < self.turns_left:
            self.turns_left -= existing.turns_left
            owner.remove_buff(existing)
            self.upgrade.do_summon(existing.turns_left)
            return
        else:
            if existing.turns_left > self.turns_left:
                existing.turns_left -= self.turns_left
            else:
                owner.remove_buff(existing)
            self.upgrade.do_summon(self.turns_left)
            return ABORT_BUFF_APPLY

class SoulDregs(Upgrade):

    def on_init(self):
        self.name = "Soul Dregs"
        self.asset = ["MissingSynergies", "Icons", "soul_dregs"]
        self.tags = [Tags.Dark, Tags.Holy]
        self.level = 5
        self.minion_health = 6
        self.minion_damage = 1
        self.owner_triggers[EventOnSpellCast] = self.on_spell_cast
    
    def get_description(self):
        return ("Whenever you cast a [holy] spell, you gain [holy] soul dregs with duration equal to the level of the spell cast.\n"
                "Whenever you cast a [dark] spell, you gain [dark] soul dregs with duration equal to the level of the spell cast.\n"
                "If you would have both [holy] and [dark] soul dregs, consume 1 remaining turn from each type until only one type is left, then summon a number of soulfly swarms equal to the number of pairs consumed.\n"
                "Soulfly swarms are flying [holy] [undead] minions with [{minion_health}_HP:minion_health] and melee attacks that deal [{minion_damage}_holy:holy] damage.").format(**self.fmt_dict())

    def on_spell_cast(self, evt):
        if not evt.spell.level:
            return
        if Tags.Holy in evt.spell.tags:
            self.owner.apply_buff(HolySoulDregsBuff(self), evt.spell.level)
        if Tags.Dark in evt.spell.tags:
            self.owner.apply_buff(DarkSoulDregsBuff(self), evt.spell.level)

    def do_summon(self, num):
        minion_health = self.get_stat("minion_health")
        minion_damage = self.get_stat("minion_damage")
        for _ in range(num):
            unit = Unit()
            unit.name = "Soulfly Swarm"
            unit.asset = ["MissingSynergies", "Units", "soulfly_swarm"]
            unit.tags = [Tags.Holy, Tags.Dark, Tags.Undead]
            unit.resists[Tags.Holy] = 100
            unit.resists[Tags.Physical] = 75
            unit.resists[Tags.Ice] = -50
            unit.flying = True
            unit.max_hp = minion_health
            unit.spells = [SimpleMeleeAttack(damage=minion_damage, damage_type=Tags.Holy)]
            self.summon(unit, radius=5, sort_dist=False)

class PureglassKnightBuff(Buff):

    def __init__(self, spell):
        self.spell = spell
        Buff.__init__(self)
    
    def on_init(self):
        self.name = "Pureglass"
        self.color = Tags.Glass.color
        self.description = "Whenever this unit loses SH, it has a 25% chance to summon another knight with 1 SH."
        self.shards = self.spell.get_stat("shards")
        self.radius = self.spell.get_stat("minion_range")
        self.phase = self.spell.get_stat("phase")
        self.damage = self.spell.get_stat("minion_damage")
        self.owner_triggers[EventOnPreDamaged] = self.on_pre_damaged
    
    def on_pre_damaged(self, evt):
        if evt.damage <= 0 or self.owner.resists[evt.damage_type] >= 100 or self.owner.shields <= 0:
            return
        if self.shards:
            targets = [unit for unit in self.owner.level.get_units_in_ball(self.owner, self.radius) if are_hostile(unit, self.owner)]
            if not self.phase:
                targets = [unit for unit in targets if self.owner.level.can_see(unit.x, unit.y, self.owner.x, self.owner.y)]
            if targets:
                self.owner.level.queue_spell(self.shard(random.choice(targets)))
        if random.random() < 0.25:
            self.spell.summon_knight(self.owner, minor=True)

    def shard(self, target):
        for point in Bolt(self.owner.level, self.owner, target, find_clear=False):
            self.owner.level.show_effect(point.x, point.y, Tags.Glassification)
            yield
        target.deal_damage(self.damage, Tags.Physical, self)

class PureglassKnightSpell(Spell):

    def on_init(self):
        self.name = "Pureglass Knight"
        self.asset = ["MissingSynergies", "Icons", "pureglass_knight"]
        self.tags = [Tags.Holy, Tags.Arcane, Tags.Conjuration]
        self.level = 6
        self.max_charges = 3
        self.must_target_empty = True
        self.must_target_walkable = True

        self.minion_health = 90
        self.minion_damage = 10
        self.minion_range = 6

        self.upgrades["minion_health"] = (40, 3)
        self.upgrades["glassify"] = (1, 5, "Glassifying Blade", "The knight's melee attack will inflict [glassify] for [3_turns:duration], which benefits from this spell's bonuses to [duration].")
        self.upgrades["phase"] = (1, 5, "Phase Glass", "The knight's charge attack becomes a teleport attack.")
        self.upgrades["shards"] = (1, 4, "Broken Shards", "Whenever the knight loses [SH:shields], it shoots out a glass shard at a random enemy in line of sight with range equal to this spell's [minion_range:minion_range], dealing damage equal to this spell's [minion_damage:minion_damage].\nIf you have the Phase Glass upgrade, the shard can pass through walls.")

    def fmt_dict(self):
        stats = Spell.fmt_dict(self)
        stats["shields"] = math.ceil(self.get_stat("minion_health")/10)
        return stats

    def get_description(self):
        return ("Summon a [living] [holy] [arcane] [glass] knight. It has fixed 1 HP, but gains [1_SH:shields] per 10 bonus to [minion_health:minion_health] this spell has, rounded up (currently [{shields}_SH:shields]).\n"
                "The knight has a melee attack and a charge attack with [{minion_range}_range:minion_range], both of which deal [{minion_damage}_physical:physical] damage.\n"
                "Whenever the knight loses [SH:shields], it has a 25% chance to summon another knight with [1_SH:shields].").format(**self.fmt_dict())

    def summon_knight(self, target, minor=False):
        unit = Unit()
        unit.asset = ["MissingSynergies", "Units", "pureglass_knight"]
        unit.name = "Pureglass Knight"
        unit.max_hp = 1
        unit.shields = math.ceil(self.get_stat("minion_health")/10) if not minor else 1
        unit.tags = [Tags.Living, Tags.Holy, Tags.Arcane, Tags.Glass]
        unit.resists[Tags.Holy] = 75
        unit.resists[Tags.Arcane] = 75
        minion_damage = self.get_stat("minion_damage")
        melee = SimpleMeleeAttack(damage=minion_damage)
        if self.get_stat("glassify"):
            melee.buff = GlassPetrifyBuff
            melee.buff_name = "Glassed"
            melee.buff_duration = self.get_stat("duration", base=3)
            # For my No More Scams mod
            melee.can_redeal = lambda target: target.resists[Tags.Physical] < 200 and not target.has_buff(GlassPetrifyBuff)
        leap = LeapAttack(damage=minion_damage, range=self.get_stat("minion_range"), is_leap=False, is_ghost=self.get_stat("phase"))
        leap.name = "Glass Charge"
        unit.spells = [melee, leap]
        unit.buffs = [PureglassKnightBuff(self)]
        self.summon(unit, target=target, radius=5, sort_dist=not minor)

    def cast_instant(self, x, y):
        self.summon_knight(Point(x, y))

class TransientBomberBuff(Buff):

    def __init__(self, spell):
        self.spell = spell
        Buff.__init__(self)

    def on_init(self):
        self.radius = self.spell.get_stat("radius")
        self.phase = self.spell.get_stat("phase")
        self.owner_triggers[EventOnDeath] = lambda evt: self.owner.level.queue_spell(self.boom())
    
    def boom(self):
        damage = self.owner.max_hp
        for stage in Burst(self.owner.level, Point(self.owner.x, self.owner.y), self.radius, ignore_walls=self.phase):
            for point in stage:
                unit = self.owner.level.get_unit_at(point.x, point.y)
                for tag in [Tags.Holy, Tags.Arcane, Tags.Fire]:
                    if not unit or not are_hostile(unit, self.owner):
                        self.owner.level.show_effect(point.x, point.y, tag)
                    else:
                        unit.deal_damage(damage if tag == Tags.Holy else damage//2, tag, self.spell)
            yield

class TransientBomberExplosion(Spell):

    def __init__(self, buff):
        self.buff = buff
        Spell.__init__(self)
    
    def can_cast(self, x, y):
        if not Spell.can_cast(self, x, y):
            return False
        return Point(x, y) in [p for stage in Burst(self.caster.level, Point(self.owner.x, self.owner.y), self.buff.radius, ignore_walls=self.buff.phase) for p in stage]

    def get_stat(self, attr, base=None):
        if attr == "range":
            return self.buff.radius
        return Spell.get_stat(self, attr, base)

    def on_init(self):
        self.name = "Suicide Explosion"
        self.requires_los = not self.buff.phase
        self.damage_type = [Tags.Holy, Tags.Arcane, Tags.Fire]
        self.description = "Deals holy damage equal to the user's max HP then half fire and arcane damage, in a %i tile burst. Suicide attack; autocasts on death." % self.buff.radius

    def cast_instant(self, x, y):
        self.owner.cur_hp = 0
        self.owner.kill()

class EternalBomberBuff(Buff):

    def __init__(self, spell):
        self.spell = spell
        Buff.__init__(self)
    
    def on_init(self):
        self.color = Tags.Holy.color
        self.radius = self.spell.get_stat("radius")
        self.phase = self.spell.get_stat("phase")
        self.description = "On death, deal holy equal to this unit's max HP in a %i tile burst. If this unit has no reincarnations, summon another eternal bomber on a random tile.\n\nEach turn, lose all reincarnations to summon the same number of transient bombers near self." % self.radius
        self.owner_triggers[EventOnDeath] = self.on_death
        # Can't just check has_buff(ReincarnationBuff) because non-passive reincarnation gets temporarily removed while the unit is reincarnating,
        # and the order in which that triggers versus this buff is random. We have to rely on my Bugfixes mod, which changes reincarnation temporary
        # self-removal and reapplying to not trigger buff apply and buff remove events.
        self.reincarnation = None
        self.owner_triggers[EventOnBuffApply] = self.on_buff_apply
        self.owner_triggers[EventOnBuffRemove] = self.on_buff_remove
    
    def on_buff_apply(self, evt):
        if isinstance(evt.buff, ReincarnationBuff):
            self.reincarnation = evt.buff

    def on_buff_remove(self, evt):
        if evt.buff is self.reincarnation:
            self.reincarnation = None

    def on_death(self, evt):
        self.owner.level.queue_spell(self.boom())
        if not self.reincarnation:
            self.spell.summon_bomber()
    
    def boom(self):
        for stage in Burst(self.owner.level, Point(self.owner.x, self.owner.y), self.radius, ignore_walls=self.phase):
            for point in stage:
                unit = self.owner.level.get_unit_at(point.x, point.y)
                if not unit or not are_hostile(unit, self.owner):
                    self.owner.level.show_effect(point.x, point.y, Tags.Holy)
                else:
                    unit.deal_damage(self.owner.max_hp, Tags.Holy, self.spell)
            yield

    def on_advance(self):
        if not self.reincarnation:
            return        
        for _ in range(self.reincarnation.lives):
            self.spell.summon_bomber(target=self.owner, minor=True)
        self.owner.remove_buff(self.reincarnation)

class EternalBomberPhaseBomber(Upgrade):
    def on_init(self):
        self.name = "Phase Bomber"
        self.level = 4
        self.description = "Eternal Bomber no longer requires line of sight.\nBomber explosions can now pass through walls."
        self.spell_bonuses[EternalBomberSpell]["requires_los"] = -1
        self.spell_bonuses[EternalBomberSpell]["phase"] = 1

class EternalBomberSpell(Spell):

    def on_init(self):
        self.name = "Eternal Bomber"
        self.asset = ["MissingSynergies", "Icons", "eternal_bomber"]
        self.tags = [Tags.Holy, Tags.Conjuration, Tags.Sorcery]
        self.level = 3
        self.max_charges = 8
        self.range = 8
        self.must_target_empty = True
        self.must_target_walkable = True

        self.minion_health = 4
        self.minion_damage = 4
        self.damage = 4
        self.radius = 2

        self.upgrades["max_charges"] = (4, 3)
        self.upgrades["range"] = (4, 2)
        self.upgrades["radius"] = (2, 4)
        self.upgrades["extra"] = (1, 4, "Extra Bomber", "When you cast this spell, an additional transient bomber will also be summoned near the target.")
        self.add_upgrade(EternalBomberPhaseBomber())

    def get_impacted_tiles(self, x, y):
        return [p for stage in Burst(self.caster.level, Point(x, y), self.get_stat('radius'), ignore_walls=self.get_stat("phase")) for p in stage]

    def fmt_dict(self):
        stats = Spell.fmt_dict(self)
        stats["total_hp"] = self.get_stat("minion_health") + self.get_stat("minion_damage") + self.get_stat("damage")
        return stats

    def get_description(self):
        return ("Summon an immobile eternal bomber with [{total_hp}_HP:minion_health], which counts as spell damage and benefits from bonuses to [minion_health:minion_health], [minion_damage:minion_damage], and [damage]. It dies after 1 turn, and on death it deals [holy] damage equal to its max HP to enemies in a [{radius}_tile:radius] burst. If the eternal bomber dies without reincarnations, summon another eternal bomber on a random tile.\n"
                "Each turn, the eternal bomber removes all reincarnations from itself to summon a transient bomber per reincarnation removed. Transient bombers have the same HP and no special abilities, but they are mobile and their explosions also deal half [arcane] and [fire] damage.").format(**self.fmt_dict())

    def summon_bomber(self, target=None, minor=False):
        unit = Unit()
        unit.max_hp = self.get_stat("minion_health") + self.get_stat("minion_damage") + self.get_stat("damage")
        if not minor:
            unit.name = "Eternal Bomber"
            unit.asset_name = "holy_bomber"
            unit.turns_to_death = 1
            unit.tags = [Tags.Holy]
            unit.stationary = True
            unit.buffs = [EternalBomberBuff(self)]
        else:
            unit.name = "Transient Bomber"
            unit.asset_name = "prism_bomber"
            unit.tags = [Tags.Holy, Tags.Arcane, Tags.Fire]
            buff = TransientBomberBuff(self)
            unit.buffs = [buff]
            unit.spells = [TransientBomberExplosion(buff)]
        if not target:
            self.summon(unit, radius=RANGE_GLOBAL, sort_dist=False)
        else:
            self.summon(unit, target=target, radius=5)

    def cast_instant(self, x, y):
        self.summon_bomber(target=Point(x, y))
        if self.get_stat("extra"):
            self.summon_bomber(target=Point(x, y), minor=True)

class RedheartSpiderBuff(Buff):

    def on_init(self):
        self.name = "Redheart Spider"
        self.color = Tags.Spider.color
        self.radius = 0
        self.global_triggers[EventOnDeath] = self.on_death
        self.global_triggers[EventOnDamaged] = self.on_damaged
        self.global_bonuses["damage"] = 0
        self.global_bonuses["range"] = 0
    
    def get_tooltip(self):
        return "Enemies within %i tiles have their poison durations increased by 2 turns each turn, and have a 25%% chance to be stunned or go berserk for 1 turn. Spider units that die in this radius are eaten, adding their max HP to this unit's and adding 1 SH.\n\nAttacks inflict duration-stacking poison with duration equal to damage done." % self.radius

    def on_death(self, evt):
        if Tags.Spider not in evt.unit.tags or distance(evt.unit, self.owner) > self.radius:
            return
        # This can happen with Mortal Coil
        if evt.unit is self.owner:
            return
        self.owner.level.queue_spell(self.eat(evt.unit))

    def on_damaged(self, evt):
        if not isinstance(evt.source, Spell) or evt.source.caster is not self.owner:
            return
        existing = evt.unit.get_buff(Poison)
        if existing:
            existing.turns_left += evt.damage
        else:
            evt.unit.apply_buff(Poison(), evt.damage)

    def eat(self, unit):
        for point in Bolt(self.owner.level, self.owner, unit, find_clear=False):
            self.owner.level.leap_effect(point.x, point.y, Tags.Spider.color, self.owner)
            yield
        self.owner.max_hp += unit.max_hp
        self.owner.deal_damage(-unit.max_hp, Tags.Heal, self)
        self.owner.add_shields(1)
        for point in Bolt(self.owner.level, unit, self.owner, find_clear=False):
            self.owner.level.leap_effect(point.x, point.y, Tags.Spider.color, self.owner)
            yield

    def on_applied(self, owner):
        self.global_bonuses["damage"] = self.owner.max_hp//5
        self.global_bonuses["range"] = self.owner.max_hp//10
        self.radius = math.floor(math.sqrt(self.owner.max_hp))

    def on_pre_advance(self):
        self.owner.global_bonuses["damage"] -= self.global_bonuses["damage"]
        self.owner.global_bonuses["range"] -= self.global_bonuses["range"]
        self.global_bonuses["damage"] = self.owner.max_hp//5
        self.global_bonuses["range"] = self.owner.max_hp//10
        self.owner.global_bonuses["damage"] += self.global_bonuses["damage"]
        self.owner.global_bonuses["range"] += self.global_bonuses["range"]
        self.radius = math.floor(math.sqrt(self.owner.max_hp))

    def on_advance(self):
        
        effects_left = 7

        for unit in self.owner.level.get_units_in_ball(self.owner, self.radius):
            if not are_hostile(self.owner, unit):
                continue
            existing = unit.get_buff(Poison)
            if existing:
                existing.turns_left += 2
            else:
                unit.apply_buff(Poison(), 2)
            if random.random() < 0.25:
                unit.apply_buff(random.choice([Stun, BerserkBuff])(), 1)
            effects_left += 1

        # Show some graphical indication of this aura if it didnt hit much
        points = self.owner.level.get_points_in_ball(self.owner.x, self.owner.y, self.radius)
        points = [p for p in points if not self.owner.level.get_unit_at(p.x, p.y)]
        random.shuffle(points)
        for _ in range(effects_left):
            if not points:
                break
            p = points.pop()
            self.owner.level.show_effect(p.x, p.y, Tags.Poison, minor=True)

class RedheartSpiderBite(Spell):

    def __init__(self, damage, range):
        Spell.__init__(self)
        self.damage = damage
        self.range = range
        self.name = "Bite"
        self.description = "Temporarily detach the user's head to bite a target at range."
        self.damage_type = Tags.Physical

    def cast(self, x, y):
        for point in Bolt(self.caster.level, self.caster, Point(x, y), find_clear=False):
            self.caster.level.leap_effect(point.x, point.y, Tags.Spider.color, self.caster)
            yield
        self.caster.level.deal_damage(x, y, self.get_stat("damage"), self.damage_type, self)
        for point in Bolt(self.caster.level, Point(x, y), self.caster, find_clear=False):
            self.caster.level.leap_effect(point.x, point.y, Tags.Spider.color, self.caster)
            yield

class RedheartSpider(Upgrade):

    def on_init(self):
        self.name = "Redheart Spider"
        self.asset = ["MissingSynergies", "Icons", "redheart_spider"]
        self.tags = [Tags.Holy, Tags.Nature, Tags.Dark, Tags.Conjuration]
        self.level = 7
        self.minion_health = 70
        self.minion_range = 2
        self.minion_damage = 2
        self.timer = 1
        self.minion = None
        self.owner_triggers[EventOnUnitAdded] = lambda evt: self.do_summon()

    def get_description(self):
        return ("Begin each level accompanied by the Redheart Spider. If it dies, it will be summoned again after [10_turns:duration].\n"
                "The Redheart Spider is a [holy] [nature] [demon] [spider] minion with [{minion_health}_HP:minion_health] and an attack that deals [{minion_damage}_physical:physical] damage with [{minion_range}_range:minion_range]. Its attacks gain damage equal to 20% of its max HP, range equal to 10% of its max HP, and inflict duration-stacking [poison] with duration equal to damage dealt.\n"
                "The Redheart Spider has an aura with radius equal to the square root of its max HP, rounded down. Each turn, enemies in this aura have their [poison] durations increased by [2_turns:duration], and have a 25% chance to be [stunned] or go [berserk]. Whenever a [spider] dies within the aura, it will be eaten, adding its max HP to the Redheart Spider's and adding [1_SH:shields].").format(**self.fmt_dict())

    def do_summon(self):
        unit = Unit()
        unit.name = "Redheart Spider"
        unit.unique = True
        unit.asset = ["MissingSynergies", "Units", "redheart_spider"]
        unit.tags = [Tags.Holy, Tags.Nature, Tags.Demon, Tags.Spider]
        unit.max_hp = self.get_stat("minion_health")
        unit.shields = 1
        unit.resists[Tags.Holy] = 100
        unit.resists[Tags.Poison] = 100
        unit.resists[Tags.Fire] = 100
        unit.spells = [RedheartSpiderBite(self.get_stat("minion_damage"), self.get_stat("minion_range"))]
        unit.buffs = [SpiderBuff(), RedheartSpiderBuff()]
        success = self.summon(unit, radius=RANGE_GLOBAL)
        if success:
            self.minion = unit
            self.timer = 10
        else:
            self.timer = 1

    def on_advance(self):
        if all(u.team == TEAM_PLAYER for u in self.owner.level.units):
            return
        if not self.minion or not self.minion.is_alive():
            self.timer -= 1
            if self.timer <= 0:
                self.do_summon()

class InexorableDecay(Upgrade):

    def on_init(self):
        self.name = "Inexorable Decay"
        self.asset = ["MissingSynergies", "Icons", "inexorable_decay"]
        self.tags = [Tags.Dark]
        self.level = 5
        self.description = "Whenever anything tries to deal [dark] damage to an enemy, that enemy permanently loses 2 max HP.\nIf it has 2 max HP or less, it will be instantly killed."
        self.global_triggers[EventOnPreDamaged] = self.on_pre_damaged
    
    def on_pre_damaged(self, evt):
        if not are_hostile(evt.unit, self.owner) or evt.damage <= 0 or evt.damage_type != Tags.Dark:
            return
        self.owner.level.queue_spell(self.decay(evt.unit))

    def decay(self, unit):
        drain_max_hp_kill(unit, 2)
        yield

    # For my No More Scams mod
    def can_redeal(self, target, source, damage_type):
        return damage_type == Tags.Dark

class RaiseWastewight(Upgrade):

    def on_init(self):
        self.name = "Raise Wastewight"
        self.level = 5
        self.description = "When an enemy with wasting dies, it has a chance to summon a wastewight, equal to twice the percentage of max HP it has lost since it was afflicted with wasting, with a minimum of 10%.\nWastewights are [fire] [undead] minions with melee attacks that permanently drain 2 max HP, and instantly kill targets with 2 max HP or less."
        self.global_triggers[EventOnDeath] = self.on_death
    
    def on_death(self, evt):
        wasting = evt.unit.get_buff(WastingBuff)
        if not wasting or random.random() >= max(2*(wasting.max_hp - evt.unit.max_hp)/wasting.max_hp, 0.1):
            return
        
        unit = BoneKnight()
        unit.name = "Wastewight"
        unit.asset = ["MissingSynergies", "Units", "wastewight"]
        unit.tags.append(Tags.Fire)
        unit.resists[Tags.Fire] = 100
        unit.spells[0].damage_type = Tags.Fire
        unit.spells[0].onhit = lambda caster, target: drain_max_hp_kill(target, 2)
        unit.spells[0].description = "Drains 2 max HP. Targets with less than 2 max HP are instantly killed."
        # For my No More Scams mod
        unit.spells[0].can_redeal = lambda target: True
        apply_minion_bonuses(self.prereq, unit)
        self.owner.level.queue_spell(self.do_summon(unit, evt.unit))

    def do_summon(self, unit, target):
        self.prereq.summon(unit, target)
        yield

class WastefireSpell(Spell):

    def on_init(self):
        self.name = "Wastefire"
        self.asset = ["MissingSynergies", "Icons", "wastefire"]
        self.tags = [Tags.Fire, Tags.Dark, Tags.Sorcery]
        self.level = 5
        self.max_charges = 6
        self.range = 8
        self.damage = 16
        self.radius = 4

        self.upgrades["max_charges"] = (4, 3)
        self.upgrades["radius"] = (2, 3)
        self.add_upgrade(RaiseWastewight())

    def get_impacted_tiles(self, x, y):
        return [p for stage in Burst(self.caster.level, Point(x, y), self.get_stat('radius')) for p in stage]

    def get_description(self):
        return ("Permanently inflict wasting to all enemies in a [{radius}_tile:radius] burst, which deals [dark] damage to the victim equal to the amount of max HP it has lost since being afflicted with the debuff.\n"
                "Then deal [{damage}_fire:fire] damage to affected enemies, and drain max HP equal to 25% of the damage dealt; enemies with less max HP than that are instantly killed. If the enemy already has wasting, the percentage of max HP drain is doubled.").format(**self.fmt_dict())

    def cast(self, x, y):
        damage = self.get_stat("damage")
        for stage in Burst(self.caster.level, Point(x, y), self.get_stat("radius")):
            for point in stage:
                self.caster.level.show_effect(point.x, point.y, Tags.Fire)
                self.caster.level.show_effect(point.x, point.y, Tags.Dark)
                unit = self.caster.level.get_unit_at(point.x, point.y)
                if not unit or not are_hostile(unit, self.caster):
                    continue
                if unit.has_buff(WastingBuff):
                    div = 2
                else:
                    unit.apply_buff(WastingBuff(self))
                    div = 4
                dealt = unit.deal_damage(damage, Tags.Fire, self)
                if dealt:
                    drain_max_hp_kill(unit, dealt//div)
            yield

class FulguriteAlchemy(Upgrade):

    def on_init(self):
        self.name = "Fulgurite Alchemy"
        self.asset = ["MissingSynergies", "Icons", "fulgurite_alchemy"]
        self.tags = [Tags.Lightning, Tags.Arcane]
        self.level = 4
        self.description = "[Petrify] and [glassify] on enemies will now decrease [lightning] resistance by 100 rather than increase it."
        self.global_triggers[EventOnBuffApply] = self.on_buff_apply
    
    def on_buff_apply(self, evt):
        if not are_hostile(evt.unit, self.owner):
            return
        if not isinstance(evt.buff, PetrifyBuff) and not isinstance(evt.buff, GlassPetrifyBuff):
            return
        evt.unit.resists[Tags.Lightning] -= 200
        evt.buff.resists[Tags.Lightning] = -100

class ShieldBurstSpell(Spell):

    def on_init(self):
        self.name = "Shield Burst"
        self.asset = ["MissingSynergies", "Icons", "shield_burst"]
        self.tags = [Tags.Arcane, Tags.Sorcery]
        self.level = 3
        self.max_charges = 6
        self.range = 0
        self.damage = 12
        self.radius = 6

        self.upgrades["max_charges"] = (6, 3)
        self.upgrades["radius"] = (4, 2, "Radius", "Shield Burst searches for enemy targets in a greater radius around each minion.")
        self.upgrades["phase"] = (1, 4, "Phase Burst", "The bolts released by this spell can now pass through walls.")
        self.upgrades["recycle"] = (1, 5, "Shield Recycle", "If a bolt kills an enemy, or if an already dead enemy is targeted by a bolt, the ally that shot that bolt gains [1_SH:shields].")
    
    def get_impacted_tiles(self, x, y):
        points = []
        for unit in self.caster.level.units:
            if not are_hostile(unit, self.caster) and unit.shields > 0:
                points.append(Point(unit.x, unit.y))
        return points

    def get_description(self):
        return ("Each shielded ally takes a separate hit of [1_arcane:arcane] damage for every [SH:shields] they have, which ignores resistance.\n"
                "For each [SH:shields] lost this way, that ally shoots out a bolt targeting a random enemy in line of sight up to [{radius}_tiles:radius] away, dealing [{damage}_arcane:arcane] damage.").format(**self.fmt_dict())

    def bolt(self, origin, target, damage, recycle):
        for point in Bolt(self.caster.level, origin, target, find_clear=False):
            self.caster.level.show_effect(point.x, point.y, Tags.Arcane, minor=True)
            yield
        target.deal_damage(damage, Tags.Arcane, self)
        if recycle and not target.is_alive():
            origin.add_shields(1)

    def cast_instant(self, x, y):

        radius = self.get_stat("radius")
        damage = self.get_stat("damage")
        phase = self.get_stat("phase")
        recycle = self.get_stat("recycle")

        units = [unit for unit in self.caster.level.units if not are_hostile(unit, self.caster) and unit.shields > 0]
        if not units:
            return
        random.shuffle(units)

        for unit in units:
            shields = unit.shields
            for _ in range(shields):
                targets = [target for target in self.caster.level.get_units_in_ball(unit, radius) if are_hostile(unit, target)]
                if not phase:
                    targets = [target for target in targets if self.caster.level.can_see(unit.x, unit.y, target.x, target.y)]
                if not targets:
                    break
                old = unit.resists[Tags.Arcane]
                unit.resists[Tags.Arcane] = 0
                unit.deal_damage(1, Tags.Arcane, self)
                unit.resists[Tags.Arcane] = old
                self.caster.level.queue_spell(self.bolt(unit, random.choice(targets), damage, recycle))

class EmpyrealFormBuff(Buff):

    def __init__(self, spell, charges):
        self.spell = spell
        self.max_hp = charges*50
        Buff.__init__(self)

    def on_init(self):
        self.name = "Empyreal Form"
        self.color = Tags.Holy.color
        self.stack_type = STACK_TYPE_TRANSFORM
        self.transform_asset_name = os.path.join("..", "..", "mods", "MissingSynergies", "Units", "empyreal_form")
        tags = [Tags.Fire, Tags.Holy]
        if self.spell.get_stat("storm"):
            tags.extend([Tags.Ice, Tags.Lightning])
        for tag in tags:
            self.resists[tag] = 100
        if self.spell.get_stat("champion"):
            self.global_bonuses["minion_duration"] = 15
            self.global_bonuses["minion_health"] = 10
            self.global_bonuses["minion_damage"] = 5
    
    def on_applied(self, owner):
        self.owner.max_hp += self.max_hp
        self.owner.deal_damage(-self.max_hp, Tags.Heal, self.spell)

    def on_unapplied(self):
        drain_max_hp(self.owner, self.max_hp)

    def on_advance(self):
        self.owner.level.queue_spell(self.spell.boom())

class EmpyrealAscensionSpell(Spell):

    def on_init(self):
        self.name = "Empyreal Ascension"
        self.asset = ["MissingSynergies", "Icons", "empyreal_ascension"]
        self.tags = [Tags.Holy, Tags.Fire, Tags.Sorcery, Tags.Enchantment]
        self.level = 7
        self.max_charges = 1
        self.range = RANGE_GLOBAL
        self.requires_los = False
        self.can_target_self = True
        self.must_target_walkable = True
        self.radius = 6
        self.damage = 33
        self.duration = 5

        self.upgrades["radius"] = (4, 3)
        self.upgrades["storm"] = (1, 6, "Storm Herald", "Empyreal Form also grants [100_ice:ice] and [100_lightning:lightning] resistance.\nThe explosion of this spell has a chance to create thunderstorm and blizzard clouds, starting at 100% near you and decreasing to 0% at the edges of the radius.")
        self.upgrades["juggernaut"] = (1, 5, "Juggernaut", "The explosion of this spell passes through walls and has a chance to destroy walls, starting at 100% near you and decreasing to 0% at the edges of the radius.")
        self.upgrades["champion"] = (1, 5, "Divine Champion", "Empyreal Form also grants [15_minion_duration:minion_duration], [10_minion_health:minion_health], and [5_minion_damage:minion_damage].")

    def get_description(self):
        return ("Assume Empyreal Form for [{duration}_turns:duration], consuming all remaining charges of this spell to gain 50 max and current HP per charge spent, and [100_fire:fire] and [100_holy:holy] resistance. The max HP is lost when the buff expires.\n"
                "While in Empyreal Form, you release an explosion in a [{radius}_tile:radius] burst around yourself each turn, dealing [{damage}_fire:fire] or [{damage}_holy:holy] damage to enemies near you, gradually decreasing to 0 at the edges of the radius.\n"
                "You can cast this spell at 0 charge remaining during Empyreal Form, teleporting to the target tile, healing yourself for [{damage}:heal] HP and immediately releasing an explosion.").format(**self.fmt_dict())

    def can_pay_costs(self):
        if self.caster.has_buff(EmpyrealFormBuff) and self.cur_charges == 0:
            return True
        return Spell.can_pay_costs(self)

    def pay_costs(self):
        if self.cur_charges == 0:
            return
        Spell.pay_costs(self)

    def get_impacted_tiles(self, x, y):
        return [p for stage in Burst(self.caster.level, Point(x, y), self.get_stat('radius'), ignore_walls=self.get_stat("juggernaut")) for p in stage]

    def can_cast(self, x, y):
        if self.caster.has_buff(EmpyrealFormBuff):
            unit = self.caster.level.get_unit_at(x, y)
            if unit and unit is not self.caster:
                return False
            return Spell.can_cast(self, x, y)
        else:
            return x == self.caster.x and y == self.caster.y

    def boom(self):

        radius = self.get_stat("radius")
        damage = self.get_stat("damage")
        damage_bonus = damage - self.damage
        storm = self.get_stat("storm")
        duration = self.get_stat("duration", base=5)
        juggernaut = self.get_stat("juggernaut")

        power = radius + 1
        for stage in Burst(self.caster.level, Point(self.caster.x, self.caster.y), radius, ignore_walls=juggernaut):
            for point in stage:
                dtype = random.choice([Tags.Fire, Tags.Holy])
                unit = self.caster.level.get_unit_at(point.x, point.y)
                if not unit or not are_hostile(unit, self.caster):
                    self.caster.level.show_effect(point.x, point.y, dtype)
                else:
                    unit.deal_damage(math.ceil(damage*power/radius), dtype, self)
                if juggernaut and self.caster.level.tiles[point.x][point.y].is_wall() and random.random() < power/radius:
                    self.caster.level.make_floor(point.x, point.y)
                if storm and not self.caster.level.tiles[point.x][point.y].is_wall() and random.random() < power/radius:
                    if point.x == self.caster.x and point.y == self.caster.y:
                        continue
                    if random.choice([True, False]):
                        cloud = BlizzardCloud(self.caster)
                        cloud.damage += damage_bonus
                    else:
                        cloud = StormCloud(self.caster)
                        cloud.damage += 2*damage_bonus
                    cloud.duration = duration
                    cloud.source = self
                    self.caster.level.add_obj(cloud, point.x, point.y)
            power -= 1
            yield

    def cast(self, x, y):
        if self.caster.has_buff(EmpyrealFormBuff):
            if x != self.caster.x or y != self.caster.y:
                self.caster.level.show_effect(self.caster.x, self.caster.y, Tags.Translocation)
                self.caster.level.act_move(self.caster, x, y, teleport=True)
            self.caster.deal_damage(-self.get_stat("damage"), Tags.Heal, self)
            yield from self.boom()
        else:
            self.caster.apply_buff(EmpyrealFormBuff(self, self.cur_charges + 1), self.get_stat("duration"))
            self.cur_charges = 0

class IronTurtleAura(DamageAuraBuff):

    def __init__(self, spell):
        DamageAuraBuff.__init__(self, 1, [], spell.get_stat("radius"))
        self.name = "Iron Turtle Aura"
        self.color = Tags.Metallic.color
    
    def get_tooltip(self):
        return "For every 100 resistance above 100, deal 1 damage of that type to enemies in a %i tile radius per turn. Excess resistances below 100 have a chance to deal damage." % self.radius

    def on_advance(self):

        self.damage_type = []
        for tag in self.owner.resists.keys():
            if self.owner.resists[tag] > 100:
                self.damage_type.append(tag)
        if not self.damage_type:
            return

        effects_left = 7
        for unit in self.owner.level.get_units_in_ball(Point(self.owner.x, self.owner.y), self.radius):
            if not are_hostile(self.owner, unit):
                continue
            for tag in self.damage_type:
                amount = self.owner.resists[tag] - 100
                while amount > 100:
                    dealt = unit.deal_damage(1, tag, self)
                    self.damage_dealt += dealt
                    amount -= 100
                if random.random() < amount/100:
                    dealt = unit.deal_damage(1, tag, self)
                    self.damage_dealt += dealt
            effects_left -= 1

        # Show some graphical indication of this aura if it didnt hit much
        points = self.owner.level.get_points_in_ball(self.owner.x, self.owner.y, self.radius)
        points = [p for p in points if not self.owner.level.get_unit_at(p.x, p.y)]
        random.shuffle(points)
        for _ in range(effects_left):
            if not points:
                break
            p = points.pop()
            self.owner.level.show_effect(p.x, p.y, random.choice(self.damage_type), minor=True)

class IronTurtleBuff(TurtleBuff):

    def __init__(self, spell):
        TurtleBuff.__init__(self)
        self.name = "Aura Cannon"
        self.cleanse = spell.get_stat("cleanse")
        if spell.get_stat("expert"):
            self.owner_triggers[EventOnBuffApply] = self.on_buff_apply
        self.cannon = spell.get_stat("cannon")

    def on_pre_advance(self):
        if not self.cleanse:
            return
        for buff in list(self.owner.buffs):
            if buff.buff_type == BUFF_TYPE_CURSE and random.random() < 0.5:
                self.owner.remove_buff(buff)

    def on_buff_apply(self, evt):
        for tag in evt.buff.resists.keys():
            if evt.buff.resists[tag] > 0:
                self.owner.resists[tag] += 25
                evt.buff.resists[tag] += 25

    def on_advance(self):
        if not self.cannon:
            return
        for buff in self.owner.buffs:
            if not isinstance(buff, DamageAuraBuff) or buff.damage_dealt <= 0:
                continue
            units = [unit for unit in self.owner.level.get_units_in_los(self.owner) if are_hostile(unit, self.owner)]
            if not units:
                return
            amount = math.ceil(random.random()*buff.damage_dealt)
            buff.damage_dealt -= amount
            self.owner.level.queue_spell(self.bolt(random.choice(units), amount))

    def bolt(self, target, damage):
        for point in Bolt(self.owner.level, self.owner, target, find_clear=False):
            self.owner.level.show_effect(point.x, point.y, random.choice([Tags.Fire, Tags.Lightning, Tags.Physical]), minor=True)
            yield
        target.deal_damage(damage, random.choice([Tags.Fire, Tags.Lightning, Tags.Physical]), self)

class IronTurtleSpell(Spell):

    def on_init(self):
        self.name = "Iron Turtle"
        self.asset = ["MissingSynergies", "Icons", "iron_turtle"]
        self.tags = [Tags.Metallic, Tags.Nature, Tags.Conjuration]
        self.level = 4
        self.max_charges = 3
        self.must_target_empty = True
        self.must_target_walkable = True

        self.radius = 7
        self.minion_health = 95
        self.minion_damage = 20

        self.upgrades["radius"] = (3, 4)
        self.upgrades["cleanse"] = (1, 2, "Iron Constitution", "Before the start of each of its turns, each of the iron turtle's debuffs has a 50% chance to be removed.")
        self.upgrades["expert"] = (1, 6, "Defense Expert", "Whenever the iron turtle receives a buff or passive effect that increases its resistances, those resistances are increased by an additional 25 each.")
        self.upgrades["cannon"] = (1, 4, "Aura Cannon", "All of the iron turtle's damage auras store the total amount of damage they have dealt.\nEach turn, the turtle fires a shot at a random enemy in line of sight for each of its damage auras that still has damage stored, expending a random amount of the stored damage to deal that much [fire], [lightning], or [physical] damage to the target.")

    def get_description(self):
        return ("Summon a [metallic] [nature] [construct] turtle minion with [{minion_health}_HP:minion_health] and a melee attack that deals [{minion_damage}_physical:physical] damage. It has [100_poison:poison], [100_lightning:lightning], [100_ice:ice], [50_fire:fire], and [50_physical:physical] resistance.\n"
                "Whenever the turtle takes damage and is not [stunned], it withdraws into its shell for [3_turns:duration], [stunning:stun] itself while gaining [50_fire:fire], [50_lightning:lightning], and [50_physical:physical] resistances.\n"
                "For every 100 resistance above 100, the turtle deal 1 damage of that type to enemies in a [{radius}_tile:radius] radius per turn. Excess resistances below 100 have a chance to deal damage.").format(**self.fmt_dict())

    def cast_instant(self, x, y):
        unit = Unit()
        unit.name = "Iron Turtle"
        unit.asset = ["MissingSynergies", "Units", "iron_turtle"]
        unit.tags = [Tags.Metallic, Tags.Nature, Tags.Construct]
        unit.max_hp = self.get_stat("minion_health")
        unit.spells = [SimpleMeleeAttack(self.get_stat("minion_damage"))]
        unit.resists[Tags.Poison] = 100
        unit.buffs = [IronTurtleAura(self), IronTurtleBuff(self)]
        self.summon(unit, target=Point(x, y))

class FadingBuff(Buff):

    def __init__(self, spell):
        self.spell = spell
        Buff.__init__(self)
    
    def on_init(self):
        self.name = "Fading"
        self.buff_type = BUFF_TYPE_CURSE
        self.color = Tags.Arcane.color
        self.asset = ["MissingSynergies", "Statuses", "fading"]
        self.damage = self.spell.get_stat("damage")
        self.agony = self.spell.get_stat("agony")
    
    def on_attempt_apply(self, owner):
        if owner.has_buff(FadingBuff):
            return False
        if owner.turns_to_death is not None:
            self.spell.caster.apply_buff(StolenEssenceBuff(), owner.turns_to_death)
            owner.level.show_effect(owner.x, owner.y, Tags.Translocation)
            owner.cur_hp = 0
            owner.kill()
            return False
        return True

    def on_applied(self, owner):
        self.owner.turns_to_death = math.ceil(self.owner.max_hp/self.damage)
    
    def on_advance(self):
        self.spell.caster.apply_buff(StolenEssenceBuff(), math.ceil(self.damage/10))
        if self.agony:
            self.owner.level.event_manager.raise_event(EventOnPreDamaged(self.owner, self.damage, Tags.Arcane, self.spell), self.owner)
            self.owner.level.event_manager.raise_event(EventOnDamaged(self.owner, self.damage, Tags.Arcane, self.spell), self.owner)

    def on_unapplied(self):
        self.owner.turns_to_death = None

class StolenEssenceBuff(Buff):
    
    def on_init(self):
        self.name = "Stolen Essence"
        self.stack_type = STACK_DURATION
        self.color = Tags.Arcane.color
    
    def on_advance(self):
        units = [unit for unit in self.owner.level.units if not are_hostile(self.owner, unit) and unit.turns_to_death is not None]
        if not units:
            return
        random.shuffle(units)
        for unit in units:
            unit.turns_to_death += 1
            self.turns_left -= 1
            if self.turns_left <= 0:
                self.owner.remove_buff(self)
                return

class EssenceLeechSpell(Spell):

    def on_init(self):
        self.name = "Essence Leech"
        self.asset = ["MissingSynergies", "Icons", "essence_leech"]
        self.tags = [Tags.Arcane, Tags.Dark, Tags.Enchantment]
        self.level = 4
        self.max_charges = 7
        self.range = 9
        self.damage = 10
        self.radius = 3

        self.upgrades["max_charges"] = (7, 4)
        self.upgrades["requires_los"] = (-1, 2, "Blindcasting", "Essence Leech can be cast without line of sight.")
        self.upgrades["radius"] = (2, 3)
        self.upgrades["agony"] = (1, 3, "Fading Agony", "Fading enemies behave as if they have taken [arcane] damage each turn equal to this spell's [damage] stat, triggering all effects that are normally triggered when enemies are damaged.")

    def get_description(self):
        return ("Drain essence from enemies in a [{radius}_tile:radius] radius, causing them to begin fading, automatically dying after a number of turns equal to their max HP divided [{damage}:arcane], rounded up, as if they are temporarily summoned units. This number benefits from this spell's bonuses to [damage].\n"
                "Each turn, each fading enemy grants you 1 turn of Stolen Essence per 10 [damage] this spell has, rounded up. Your temporary minions will expend remaining duration of Stolen Essence before their own remaining lifetimes.\n"
                "Temporary enemies are instantly killed, and their remaining lifetimes given to you as Stolen Essence.").format(**self.fmt_dict())

    def cast_instant(self, x, y):
        for unit in self.owner.level.get_units_in_ball(Point(x, y), self.get_stat("radius")):
            if not are_hostile(unit, self.caster):
                continue
            unit.apply_buff(FadingBuff(self))

class BloodyMassBuff(Buff):

    def __init__(self, spell):
        self.spell = spell
        Buff.__init__(self)
    
    def on_init(self):
        self.name = "Bloody Regrowth"
        self.color = Tags.Demon.color
        self.description = "Regenerates 5% of its max HP per turn. When damaged, heal its summoner for half of that damage."
        self.owner_triggers[EventOnDamaged] = self.on_damaged
    
    def on_damaged(self, evt):
        self.owner.source.caster.deal_damage(-evt.damage//2, Tags.Heal, self)
    
    def on_advance(self):
        if self.owner.cur_hp < self.owner.max_hp:
            self.owner.deal_damage(-math.ceil(self.owner.max_hp/20), Tags.Heal, self)

class BloodyMassBloodSplatter(SimpleRangedAttack):

    def __init__(self, spell):
        SimpleRangedAttack.__init__(self, name="Blood Splatter", damage=spell.get_stat("minion_damage"), damage_type=Tags.Dark, range=spell.get_stat("minion_range"), radius=1)
        self.tags = [Tags.Dark]
        self.description = "Only damages enemies."
        self.bloodrage = spell.get_stat("bloodrage")
        self.duration = 10
        self.penetration = spell.get_stat("penetration")
    
    def get_penetration(self):
        summoner = self.caster.source.caster
        return math.ceil(100*(summoner.max_hp - summoner.cur_hp)/summoner.max_hp) if self.penetration else 0

    def hit(self, x, y):
        unit = self.caster.level.get_unit_at(x, y)
        if not unit or not are_hostile(unit, self.caster):
            self.caster.level.show_effect(x, y, Tags.Dark)
        else:
            penetration = self.get_penetration()
            unit.resists[Tags.Dark] -= penetration
            unit.deal_damage(self.get_stat("damage"), Tags.Dark, self)
            unit.resists[Tags.Dark] += penetration
            if self.bloodrage:
                self.caster.source.caster.apply_buff(BloodrageBuff(1), self.get_stat("duration"))

    # For my No More Scams mod
    def can_redeal(self, target):
        return target.resists[Tags.Dark] - self.get_penetration() < 100

    def get_stat(self, attr, base=None):
        bonus = 0
        if attr == "radius":
            bonus = math.floor(math.sqrt(self.owner.max_hp/10))
        if attr == "range":
            bonus = self.owner.max_hp//10
        return Spell.get_stat(self, attr, base) + bonus

class FleshSacrificeSpell(Spell):

    def on_init(self):
        self.name = "Flesh Sacrifice"
        self.asset = ["MissingSynergies", "Icons", "flesh_sacrifice"]
        self.tags = [Tags.Dark, Tags.Conjuration]
        self.level = 5
        self.max_charges = 6
        self.range = 10
        self.requires_los = False
        self.must_target_empty = True
        self.must_target_walkable = True

        self.damage = 25
        self.minion_range = 2
        self.minion_damage = 19

        self.upgrades["max_charges"] = (6, 3)
        self.upgrades["damage"] = (25, 3)
        self.upgrades["bloodrage"] = (1, 6, "Bloodbath", "Whenever the bloody mass's blood splatter hits an enemy, you gain bloodlust for [10_turns:duration], increasing the damage of all of your spells by 1.\nThis duration benefits from your bonuses to [duration].")
        self.upgrades["penetration"] = (1, 5, "Power of Pain", "The bloody mass's blood splatter penetrates enemies' [dark] resistance by an amount equal to your percentage of missing HP.")
    
    def get_description(self):
        return ("Sacrifice some of your flesh and blood, dealing [{damage}_dark:dark] damage to yourself and summoning a bloody mass with max HP equal to twice the damage dealt, or teleport an existing bloody mass to the target tile and add to its max HP.\n"
                "The bloody mass is a [living] [demon] minion that regenerates 5% of its max HP per turn. Whenever it takes damage, you recover the lost flesh, healing yourself for half of the damage taken. It has a blood splatter attack with [{minion_range}_range:minion_range], [1_radius:radius], and [{minion_damage}_dark:dark] damage, which gains bonus range equal to 10% of its max HP and bonus radius equal to the square root of that amount, rounded down. It otherwise benefits from your stat bonuses rather than its own.").format(**self.fmt_dict())

    def get_impacted_tiles(self, x, y):
        return [Point(x, y)]

    def cast_instant(self, x, y):

        dealt = self.caster.deal_damage(self.get_stat("damage"), Tags.Dark, self)
        if not dealt:
            return
        
        existing = None
        for unit in self.caster.level.units:
            if unit.source is self:
                existing = unit
                break
        if existing:
            existing.max_hp += dealt
            existing.deal_damage(-dealt, Tags.Heal, self)
            self.caster.level.show_effect(existing.x, existing.y, Tags.Translocation)
            self.caster.level.act_move(existing, x, y, teleport=True)
            return
        
        unit = Unit()
        unit.unique = True
        unit.name = "Bloody Mass"
        unit.asset = ["MissingSynergies", "Units", "bloody_mass"]
        unit.max_hp = 2*dealt
        unit.tags = [Tags.Demon, Tags.Living]
        unit.resists[Tags.Physical] = -50
        spell = BloodyMassBloodSplatter(self)
        spell.statholder = self.caster
        unit.spells = [spell]
        unit.buffs = [BloodyMassBuff(self)]
        self.summon(unit, Point(x, y))

class QuantumOverlayBuff(Buff):

    def __init__(self, spell):
        self.spell = spell
        Buff.__init__(self)

    def on_init(self):
        self.name = "Quantum Overlay"
        self.color = Tags.Arcane.color
        self.stack_type = STACK_REPLACE
        if self.spell.get_stat("bifurcation"):
            self.global_bonuses["num_targets"] = 1
        self.overlays = self.spell.get_stat("overlays")
        self.global_triggers[EventOnDamaged] = self.on_damaged
        self.group = self.spell.get_stat("group")

    def on_damaged(self, evt):

        if evt.source is self.spell:
            return

        if evt.unit is self.owner or (self.group and not are_hostile(evt.unit, self.owner)):
            for _ in range(self.overlays):
                evt.unit.deal_damage(evt.damage//4, evt.damage_type, self.spell)
        
        if not evt.source or not evt.source.owner:
            return
        
        if evt.source.owner is not self.owner and (not self.group or are_hostile(evt.source.owner, self.owner)):
            return

        for _ in range(self.overlays):
            evt.unit.deal_damage(evt.damage//2, evt.damage_type, self.spell)

class QuantumOverlaySpell(Spell):

    def on_init(self):
        self.name = "Quantum Overlay"
        self.asset = ["MissingSynergies", "Icons", "quantum_overlay"]
        self.tags = [Tags.Chaos, Tags.Arcane, Tags.Enchantment]
        self.level = 6
        self.max_charges = 3
        self.range = 0

        self.duration = 5
        self.overlays = 1

        self.upgrades["duration"] = (5, 3)
        self.upgrades["overlays"] = (1, 5, "Double Overlay", "Quantum Overlay will now redeal damage an additional time, to both you and enemies.")
        self.upgrades["group"] = (1, 5, "Group Overlay", "Quantum Overlay now also affects damage dealt to and by your minions.")
        self.upgrades["bifurcation"] = (1, 4, "Bifurcation", "For its duration, Quantum Overlay now gives a bonus of [1:num_targets] to [num_targets:num_targets].")
    
    def get_description(self):
        return ("The existence of another you from a parallel world is partially overlaid onto yours.\n"
                "Whenever you deal damage, this spell redeals 50% of that damage to the same target. Whenever you take damage, this spell redeals 25% of that damage to you.\n"
                "This spell cannot trigger itself.\n"
                "Lasts [{duration}_turns:duration].").format(**self.fmt_dict())

    def cast_instant(self, x, y):
        self.caster.apply_buff(QuantumOverlayBuff(self), self.get_stat("duration"))

class FracturedMemories(Upgrade):

    def on_init(self):
        self.name = "Fractured Memories"
        self.asset = ["MissingSynergies", "Icons", "fractured_memories"]
        self.tags = [Tags.Arcane, Tags.Chaos]
        self.level = 5
        self.description = "Each turn, each enemy has a 0.5% chance to be [stunned] or go [berserk] per total level of spells you have.\nThe duration of these debuffs is [1_turn:duration], which is unaffected by bonuses."
    
    def on_advance(self):
        level = 0
        for spell in self.owner.spells:
            level += spell.level
        for unit in list(self.owner.level.units):
            if not are_hostile(unit, self.owner) or random.random() >= level*0.005:
                continue
            unit.apply_buff(random.choice([Stun, BerserkBuff])(), 1)

class Ataraxia(Upgrade):

    def on_init(self):
        self.name = "Ataraxia"
        self.asset = ["MissingSynergies", "Icons", "ataraxia"]
        self.tags = [Tags.Sorcery, Tags.Enchantment, Tags.Conjuration]
        self.level = 7
        self.description = "For every 2 unspent SP you have, all spells and skills gain [1_damage:damage] and [1_minion_health:minion_health].\nFor every 4 unspent SP you have, all spells and skills gain [1_range:range], [1_duration:duration], [1_minion_damage:minion_damage], [1_minion_duration:minion_duration], and [1_cascade_range:cascade_range].\nFor every 8 unspent SP you have, all spells and skills gain [1_num_targets:num_targets], [1_minion_range:minion_range], and [1_num_summons:num_summons].\nAll spells and skills gain bonus [radius] equal to the square root of 1/8 of your unspent SP, rounded down."
        # Don't use self.global_bonuses, otherwise the description becomes too long
        self.bonuses = defaultdict(lambda: 0)
        self.owner_triggers[EventOnBuffApply] = self.on_buff_apply

    def update_stat(self, stat, value):
        self.owner.global_bonuses[stat] -= self.bonuses[stat]
        self.bonuses[stat] = value
        self.owner.global_bonuses[stat] += value

    def on_advance(self):
        for stat in ["damage", "minion_health"]:
            self.update_stat(stat, self.owner.xp//2)
        for stat in ["range", "duration", "minion_damage", "minion_duration", "cascade_range"]:
            self.update_stat(stat, self.owner.xp//4)
        for stat in ["num_targets", "minion_range", "num_summons"]:
            self.update_stat(stat, self.owner.xp//8)
        self.update_stat("radius", math.floor(math.sqrt(self.owner.xp/8)))

    def on_applied(self, owner):
        self.on_advance()

    def on_add_spell(self, spell):
        self.on_advance()

    def on_buff_apply(self, evt):
        if not isinstance(evt.buff, Upgrade):
            return
        self.on_advance()

class StaticBuff(Buff):

    def __init__(self, spell):
        self.spell = spell
        Buff.__init__(self)
    
    def on_init(self):
        self.name = "Static"
        self.asset = ["MissingSynergies", "Statuses", "static"]
        self.color = Tags.Lightning.color
        self.buff_type = BUFF_TYPE_CURSE
        self.stack_type = STACK_INTENSITY
        self.shocking = self.spell.get_stat("shocking")
        self.owner_triggers[EventOnBuffApply] = self.on_buff_apply
    
    def discharge(self, stun):
        if not self.owner.gets_clarity and random.random() < 0.5:
            stun.turns_left += 1
        if self.shocking:
            # Queue this so it triggers after Fulgurite Alchemy
            self.owner.level.queue_spell(self.shock())
    
    def shock(self):
        self.owner.deal_damage(2, Tags.Lightning, self.spell)
        yield

    def on_applied(self, owner):
        stuns = []
        for buff in self.owner.buffs:
            if isinstance(buff, Stun):
                stuns.append(buff)
        if stuns:
            self.discharge(random.choice(stuns))
            return ABORT_BUFF_APPLY
    
    def on_buff_apply(self, evt):
        if not isinstance(evt.buff, Stun):
            return
        self.discharge(evt.buff)
        self.owner.remove_buff(self)

class StaticFieldBuff(DamageAuraBuff):

    def __init__(self, spell):
        self.spell = spell
        DamageAuraBuff.__init__(self, damage=2, damage_type=Tags.Lightning, radius=spell.get_stat("radius"))
        self.name = "Static Field"
        self.spontaneous = spell.get_stat("spontaneous")

    def on_advance(self):

        effects_left = 7

        for unit in self.owner.level.get_units_in_ball(Point(self.owner.x, self.owner.y), self.radius):
            if not are_hostile(unit, self.owner):
                continue
            self.damage_dealt += unit.deal_damage(2, Tags.Lightning, self.spell)
            unit.apply_buff(StaticBuff(self.spell))
            if self.spontaneous and random.random() < unit.get_buff_stacks(StaticBuff)*0.05:
                unit.apply_buff(Stun(), 1)
            effects_left -= 1

        # Show some graphical indication of this aura if it didnt hit much
        points = self.owner.level.get_points_in_ball(self.owner.x, self.owner.y, self.radius)
        points = [p for p in points if not self.owner.level.get_unit_at(p.x, p.y)]
        random.shuffle(points)
        for _ in range(effects_left):
            if not points:
                break
            p = points.pop()
            self.owner.level.show_effect(p.x, p.y, Tags.Lightning, minor=True)

class StaticFieldSpell(Spell):

    def on_init(self):
        self.name = "Static Field"
        self.asset = ["MissingSynergies", "Icons", "static_field"]
        self.tags = [Tags.Lightning, Tags.Enchantment]
        self.level = 5
        self.max_charges = 3
        self.range = 0
        self.radius = 7
        self.duration = 30

        self.upgrades["radius"] = (3, 3)
        self.upgrades["duration"] = (15, 2)
        self.upgrades["shocking"] = (1, 4, "Shocking Discharge", "When a stack of static is discharged from an enemy, it deals [2_lightning:lightning] damage, which is fixed and cannot be increased using shrines, skills, or buffs.\nThis damage occurs even if the enemy can gain clarity.")
        self.upgrades["spontaneous"] = (1, 4, "Spontaneous Discharge", "Each turn, Static Field has a 10% chance to [stun] each enemy in its radius for [1_turn:duration], which does not benefit from bonuses but can be extended by static.\nThe chance is equal to the target's number of static stacks times 5%.")
    
    def get_description(self):
        return ("For [{duration}_turns:duration], deal [2_lightning:lightning] damage and apply a stack of static per turn to each enemy in a [{radius}_tile:radius] radius. This damage is fixed, and cannot be increased using shrines, skills, or buffs.\n"
                "When an enemy is inflicted with [stun], [freeze], [petrify], [glassify], or a similar incapacitating debuff, discharge all stacks of static on it. Each stack discharged has an independent 50% chance to increase the duration of that debuff by [1_turn:duration]. Static will be discharged immediately if applied to a target that already has one of these debuffs.\n"
                "Static cannot extend debuff duration on a target that can gain clarity.").format(**self.fmt_dict())

    def cast_instant(self, x, y):
        self.caster.apply_buff(StaticFieldBuff(self), self.get_stat("duration"))

all_player_spell_constructors.extend([WormwoodSpell, IrradiateSpell, FrozenSpaceSpell, WildHuntSpell, PlanarBindingSpell, ChaosShuffleSpell, BladeRushSpell, MaskOfTroublesSpell, PrismShellSpell, CrystalHammerSpell, ReturningArrowSpell, WordOfDetonationSpell, WordOfUpheavalSpell, RaiseDracolichSpell, EyeOfTheTyrantSpell, TwistedMutationSpell, ElementalChaosSpell, RuinousImpactSpell, CopperFurnaceSpell, GenesisSpell, OrbOfFleshSpell, EyesOfChaosSpell, DivineGazeSpell, WarpLensGolemSpell, MortalCoilSpell, MorbidSphereSpell, GoldenTricksterSpell, RainbowEggSpell, SpiritBombSpell, OrbOfMirrorsSpell, VolatileOrbSpell, AshenAvatarSpell, AstralMeltdownSpell, ChaosHailSpell, UrticatingRainSpell, ChaosConcoctionSpell, HighSorcerySpell, MassOfCursesSpell, BrimstoneClusterSpell, CallScapegoatSpell, FrigidFamineSpell, NegentropySpell, GatheringStormSpell, WordOfRustSpell, LiquidMetalSpell, LivingLabyrinthSpell, AgonizingStormSpell, PsychedelicSporesSpell, KingswaterSpell, ChaosTheorySpell, AfterlifeEchoesSpell, TimeDilationSpell, CultOfDarknessSpell, BoxOfWoeSpell, MadWerewolfSpell, ParlorTrickSpell, GrudgeReaperSpell, DeathMetalSpell, MutantCyclopsSpell, PrimordialRotSpell, CosmicStasisSpell, WellOfOblivionSpell, AegisOverloadSpell, PureglassKnightSpell, EternalBomberSpell, WastefireSpell, ShieldBurstSpell, EmpyrealAscensionSpell, IronTurtleSpell, EssenceLeechSpell, FleshSacrificeSpell, QuantumOverlaySpell, StaticFieldSpell])
skill_constructors.extend([ShiveringVenom, Electrolysis, BombasticArrival, ShadowAssassin, DraconianBrutality, RazorScales, BreathOfAnnihilation, AbyssalInsight, OrbSubstitution, LocusOfEnergy, DragonArchmage, SingularEye, Hydromancy, NuclearWinter, UnnaturalVitality, ShockTroops, ChaosTrick, SoulDregs, RedheartSpider, InexorableDecay, FulguriteAlchemy, FracturedMemories, Ataraxia])