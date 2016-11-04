#!/usr/bin/python2
import tcod as libtcod
import math
import textwrap
import shelve

SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50

MAP_WIDTH = 80
MAP_HEIGHT = 43

BAR_WIDTH = 20
PANEL_HEIGHT = 7
PANEL_Y = SCREEN_HEIGHT - PANEL_HEIGHT

INVENTORY_WIDTH = 50

MSG_X = BAR_WIDTH +2
MSG_WIDTH = SCREEN_WIDTH - BAR_WIDTH -2
MSG_HEIGHT = PANEL_HEIGHT -1

ROOM_MAX_SIZE = 10
ROOM_MIN_SIZE = 6
MAX_ROOMS = 30

MAX_ROOM_MONSTERS = 3
MAX_ROOM_ITEMS = 2

LIMIT_FPS = 20

FOV_ALGO = 0
FOV_LIGHT_WALLS = True
TORCH_RADIUS = 10

PLAYER_SPEED = 1
DEFAULT_SPEED = 8
DEFAULT_ATTACK_SPEED = 20

HEAL_AMOUNT = 5
CONFUSE_NUM_TURNS = 10
CONFUSE_RANGE = 6
FIREBALL_RADIUS = 3
FIREBALL_DAMAGE = 12


color_dark_wall = libtcod.Color(10, 10, 100)
color_light_wall = libtcod.Color(130, 11, 50)
color_dark_ground = libtcod.Color(50, 50, 150)
color_light_ground = libtcod.Color(200, 180, 50)


class Rect:
    #a rectangle on the map. used to characterize a room
    def __init__(self, x, y, w, h):
        self.x1 = x
        self.y1 = y
        self.x2 = x + w
        self.y2 = y + h

    def center(self):
        center_x = (self.x1 + self.x2)/2
        center_y = (self.y1 + self.y2)/2
        return (center_x, center_y)

    def intersect(self, other):
        #return true if this rectangle intersects with the given
        return(self.x1 <= other.x2 and self.x2 >= other.x1 and self.y1 <= other.y2 and self.y2 >= other.y1)

class Tile:
    #a tile of the map and its properties
    def __init__(self,blocked,block_sight = None):
        self.blocked = blocked
        self.explored = False    
        #by default if a tile is blocked it also blocks sight
        if block_sight is None: block_sight = blocked
        self.block_sight = block_sight

class Object:
    #This is a genaric object: the play, a monster, an item , stairs
    # its always represented by a character on the screen
    def __init__(self,x,y,char,name,color,blocks = False, fighter=None, ai=None,speed = DEFAULT_SPEED,item = None):
        self.x = x
        self.y = y
        self.char = char
        self.color = color
        self.name = name
        self.blocks = blocks

        self.item = item
        if self.item:
            self.item.owner = self

        self.fighter = fighter
        if self.fighter: #let the fighter component know who owns it
            self.fighter.owner = self
        self.ai = ai
        if self.ai: #let the Ai component know who owns it
            self.ai.owner = self

        self.speed = speed
        self.wait = 0

    def move(self,dx,dy):
        #move by the given delta's
        if not is_blocked(self.x +dx, self.y +dy):
            self.x += dx
            self.y += dy
        
        self.wait = self.speed
    
    def move_towards(self, target_x, target_y):
        #vector from this object to the target, and distance
        dx = target_x - self.x
        dy = target_y - self.y
        distance = math.sqrt(dx ** 2 + dy ** 2)

        #normalize it to length 1 (preserving direction)
        #round and convert to int so we cant walk off the map
        dx = int(round(dx/distance))
        dy = int(round(dy/distance))
        self.move(dx, dy)

    def distance_to(self, other):
        #return the distance to another object
        dx = other.x - self.x
        dy = other.y - self.y
        return math.sqrt(dx **2 + dy **2)
    
    def distance(self, x, y):
        return math.sqrt((x - self.x) ** 2 + (y - self.y) ** 2)

    def draw(self):
        #set the color then draw the character that represents this object in its position 
        if libtcod.map_is_in_fov(fov_map, self.x, self.y):
            libtcod.console_set_default_foreground(con,self.color)
            libtcod.console_put_char(con,self.x,self.y,self.char,libtcod.BKGND_NONE)

    def send_to_back(self):
        global objects
        objects.remove(self)
        objects.insert(0,self)

    def clear(self):
        #erase the character that represents the object
        libtcod.console_put_char(con,self.x,self.y,' ',libtcod.BKGND_NONE)

class Fighter:
    #combat-related properties and methods (monster, player, npc)
    def __init__(self, hp, defense, power, death_function=None, attack_speed = DEFAULT_ATTACK_SPEED):
        self.max_hp = hp
        self.hp = hp
        self.defense = defense
        self.power = power
        self.death_function = death_function
        self.attack_speed = attack_speed

    def take_damage(self,damage):
        if damage>0:
            self.hp -= damage

            if self.hp <= 0:
                function = self.death_function
                if function is not None:
                    function(self.owner)

    def attack(self, target):
        damage = self.power - target.fighter.defense

        if damage >0:
            message(self.owner.name.capitalize() + ' attacks ' + target.name + ' for ' +str(damage))
            target.fighter.take_damage(damage)
        else:
            message(self.owner.name.capitalize() + ' attacks '+ target.name +' but it does nothing!')
        
        self.owner.wait = self.attack_speed
    def heal(self, amount):
        self.hp += amount
        if(self.hp >self.max_hp):
            self.hp = self.max_hp

class DragonAI:
    def __inti__(self):
        self.state = 'chasing'

    #def take_turn(self):
       # if self.state == 'chasing':
            

class BasicMonster:
    #AI for a basic monster.
    def take_turn(self):
        monster = self.owner
        if libtcod.map_is_in_fov(fov_map, monster.x, monster.y):
            if monster.distance_to(player) >=2:
                monster.move_towards(player.x,player.y)
            
            elif player.fighter.hp > 0:
                monster.fighter.attack(player)
    
class ConfusedMonster:
    def __init__(self, old_ai, num_turns = CONFUSE_NUM_TURNS):
        self.old_ai = old_ai
        self.num_turns = num_turns

    def take_turn(self):
        if self.num_turns > 0: #still confused
            #move in a random direction and decrease the number of turns confused
            self.owner.move(libtcod.random_get_int(0, -1,-1), libtcod.random_get_int(0, -1, -1))
            self.num_turns -=1
        else:
           self.owner.ai = self.old_ai
           message('The ' + self.owner.name + ' is no longer confused', libtcod.red)

class Item:
    #an item that can be picked up and used
    def __init__(self, use_function=None):
        self.use_function = use_function

    def pick_up(self):
        #add to player inventory from the map
        if len(inventory) >=26:
            message('Your invetory is full,cannot pick up, '+ self.owner.name + ' man you should hit the gym more', libtcod.red)
        else:
            inventory.append(self.owner)
            objects.remove(self.owner)
            message('You picked up a '+ self.owner.name + '!',libtcod.green)
    def use(self):
        if self.use_function is None:
            message('The ' + self.owner.name + ' is too good for you')
        else:
            if self.use_function() != 'cancelled':
                inventory.remove(self.owner) #destroy the item after use unless its canceled somehow

    def drop(self):
        objects.append(self.owner)
        inventory.remove(self.owner)
        self.owner.x = player.x
        self.owner.y = player.y
        message('You dropped a ' + self.owner.name + '.',libtcod.yellow)

def target_tile(max_range=None):
    global key,mouse
    while True:
        libtcod.console_flush()
        libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS | libtcod.EVENT_MOUSE, key, mouse)
        render_all()

        (x ,y) = (mouse.cx,mouse.cy)

        if mouse.lbutton_pressed:
            return (x, y)

        if mouse.rbutton or key.vk == libtcod.KEY_ESCAPE:
            return (None, None) #exit if teh player hits right click or escape


def handle_keys():
    global key
    global fov_recompute
    global playerx, playery
    global stairs
    
    #realtime Not needed when mouse and keyboard are configured
    #key = libtcod.console_check_for_keypress()
    #turn based
    #key = libtcod.console_wait_for_keypress()
    if key.vk == libtcod.KEY_ENTER and key.lalt:
        #alt enter to full screen
        libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())
    elif key.vk == libtcod.KEY_ESCAPE:
        #escape exits game
        return 'exit' 

    if player.wait >0:
        player.wait -= 1
        return

    if game_state == 'playing':
        #movement keys
        if libtcod.console_is_key_pressed(libtcod.KEY_UP):
            player_move_or_attack(0,-1)
        elif libtcod.console_is_key_pressed(libtcod.KEY_DOWN):
            player_move_or_attack(0,1)
        elif libtcod.console_is_key_pressed(libtcod.KEY_LEFT):
            player_move_or_attack(-1,0)
        elif libtcod.console_is_key_pressed(libtcod.KEY_RIGHT):
            player_move_or_attack(1,0)
        else:
            #test other keys
            key_char = chr(key.c)
            if key_char == 'd':
                chosen = inventory_menu("Press the key to drop the item, any other key to cancel\n")
                if chosen is not None:
                    chosen.drop()
            if key_char == 'g':
                #pick up and item
                for object in objects:
                    if object.x == player.x and object.y == player.y and object.item:
                        object.item.pick_up()
                        break
            if key_char == 'i':
                chosen = inventory_menu('To use an item press the key next to it, any other key will close the window \n')
                if chosen is not None:
                    chosen.use()
            if key_char == '<' or key_char == '>':
                #go down stairs if the player is on them
                if stairs.x == player.x and stairs.y == player.y:
                    next_level()
            return 'didnt-take-turn'

def get_names_under_mouse():
    global mouse

    #return a string with the names of all objects under the mouse
    (x, y) = (mouse.cx, mouse.cy)

    #create a list with the names of all objects at teh mouse coordinates and in FOV
    names = [obj.name for obj in objects
        if obj.x == x and obj.y ==y and libtcod.map_is_in_fov(fov_map, obj.x, obj.y)]

    names = ', '.join(names)
    return names.capitalize()

def make_map():
    global map, objects, stairs

    objects = [player]

    #fill the map with "blocked" tiles
    map = [[Tile(True)
        for y in range(MAP_HEIGHT)]
            for x in range(MAP_WIDTH)] 
    # RANDOM DUNGEON GENERATION GOGOGOG
    rooms = []
    num_rooms = 0

    for r in range(MAX_ROOMS):
        #random width and height
        w = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
        h = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
        #random position within boundaries of the map
        x = libtcod.random_get_int(0, 0, MAP_WIDTH -w -1)
        y = libtcod.random_get_int(0, 0, MAP_HEIGHT - h -1)
        #make a rectangle with those numbers
        new_room = Rect(x, y, w, h)

        #confirm room is ok
        failed = False
        for other_room in rooms:
            if new_room.intersect(other_room):
                failed = True
                break
        
        if not failed:
            create_room(new_room)
            (new_x, new_y) = new_room.center()
            
            if num_rooms == 0:
                #if its the furst room put the player there
                player.x = new_x
                player.y = new_y
            else:
                #connect to the other rooms

                #center coordinates of previous room
                (prev_x, prev_y) = rooms[num_rooms-1].center()

                if libtcod.random_get_int(0, 0, 1) == 1:
                    #horrizontal first
                    create_h_tunnel(prev_x, new_x, prev_y)
                    create_v_tunnel(prev_y, new_y, new_x)
                else:
                    #vertical first
                    create_v_tunnel(prev_y, new_y, prev_x)
                    create_h_tunnel(prev_x, new_x, new_y)
           
            place_objects(new_room)
            rooms.append(new_room)
            num_rooms += 1

    #second floor
    #create stairs
    stairs = Object(new_x, new_y, '<', 'Stairs', libtcod.white)        
    objects.append(stairs)
    stairs.send_to_back() #Drawn below the monsters

def render_all():
    global color_light_wall, color_dark_wall
    global color_light_ground, color_dark_ground
    global fov_recompute

    if fov_recompute:
        fov_recompute = False
        libtcod.map_compute_fov(fov_map, player.x, player.y, TORCH_RADIUS, FOV_LIGHT_WALLS, FOV_ALGO)
    #go through all tiles and set their background colour
  
    for y in range(MAP_HEIGHT):
        for x in range(MAP_WIDTH):
            visible = libtcod.map_is_in_fov(fov_map, x, y)
            wall = map[x][y].block_sight
            if not visible:
                if map[x][y].explored:
                    if wall:
                        libtcod.console_set_char_background(con, x, y, color_dark_wall, libtcod.BKGND_SET)
                    else:
                        libtcod.console_set_char_background(con, x, y, color_dark_ground, libtcod.BKGND_SET)
            else:
                if wall:
                    libtcod.console_set_char_background(con, x, y, color_light_wall, libtcod.BKGND_SET)
                else:
                    libtcod.console_set_char_background(con, x, y, color_light_ground, libtcod.BKGND_SET)
                map[x][y].explored = True

    #draw all objects in the list
    for object in objects:
        object.draw()
    player.draw()
    
    #blit contents of con to display
    libtcod.console_blit(con,0,0,SCREEN_WIDTH,SCREEN_HEIGHT,0,0,0)
  
    #player stat display
    libtcod.console_set_default_background(panel, libtcod.black)
    libtcod.console_clear(panel)

    #render gui panel
    y = 1
    for(line, color) in game_msgs:
        libtcod.console_set_default_foreground(panel, color)
        libtcod.console_print_ex(panel, MSG_X, y, libtcod.BKGND_NONE, libtcod.LEFT, line)
        y +=1

    render_bar(1, 1, BAR_WIDTH, 'HP', player.fighter.hp, player.fighter.max_hp, libtcod.light_red, libtcod.darker_red)

    #render mouse hover names
    libtcod.console_set_default_foreground(panel, libtcod.light_grey)
    libtcod.console_print_ex(panel, 1, 0, libtcod.BKGND_NONE, libtcod.LEFT, get_names_under_mouse())

    #blit contents of panel to display (bars and messages)
    libtcod.console_blit(panel, 0, 0, SCREEN_WIDTH, PANEL_HEIGHT, 0, 0, PANEL_Y)

def create_room(room):
    global map

    for x in range(room.x1 + 1, room.x2):
        for y in range(room.y1 +1, room.y2):
            map[x][y].blocked = False
            map[x][y].block_sight = False
def create_h_tunnel(x1, x2, y):
    global map
    #create a horizontal tunnel between two rooms 
    for x in range(min(x1, x2), max(x1, x2) + 1):
        map[x][y].blocked = False
        map[x][y].block_sight = False

def create_v_tunnel(y1, y2, x):
    global map
    #create a vertical tunnel between two rooms
    for y in range(min(y1, y2), max(y1, y2) + 1):
        map[x][y].blocked = False
        map[x][y].block_sight = False

def place_objects(room):
    #as we stand objects must be monsters
    #choose a random number of monsters
    num_monsters = libtcod.random_get_int(0, 0, MAX_ROOM_MONSTERS)

    for i in range(num_monsters):
        #choose a random spot for the monster
        x = libtcod.random_get_int(0, room.x1+1, room.x2-1)
        y = libtcod.random_get_int(0, room.y1+1, room.y2-1)
        if not is_blocked(x, y):
            choice = libtcod.random_get_int(0,0,100)
            if choice< 40: #40% chance of orc
                #ORC
                stats = Fighter(hp=10, defense=0, power=3, death_function = monster_death)
                ai_comp = BasicMonster()
                monster = Object(x, y, 'o', 'orc', libtcod.desaturated_green, blocks = True, fighter=stats, ai=ai_comp)
            elif choice ==41: #1% chance of Alec
                stats = Fighter(hp=50, defense=0, power=0, death_function = monster_death)
                ai_comp = BasicMonster()
                monster = Object(x, y, 'A', 'Alec', libtcod.orange, blocks = True, fighter=stats, ai=ai_comp)
            elif choice > 41 and choice <70:
                stats = Fighter(hp=5, defense= 1, power = 1, death_function = monster_death)
                ai_comp = BasicMonster()
                monster = Object(x, y, 'J', 'Jacobi', libtcod.light_purple, blocks = True, fighter = stats, ai=ai_comp)
            else:
                #TROLL
                stats = Fighter(hp=16, defense=1, power=4, death_function = monster_death)
                ai_comp = BasicMonster()
                monster = Object(x, y, 'T', 'Troll', libtcod.darker_green, blocks = True, fighter=stats, ai=ai_comp)
            objects.append(monster)

    #items now
    num_items = libtcod.random_get_int(0, 0, MAX_ROOM_ITEMS)

    for i in range(num_items):
        #choose a random spot for the item
        x = libtcod.random_get_int(0, room.x1+1, room.x2-1)
        y = libtcod.random_get_int(0, room.y1+1, room.y2-1)

        if not is_blocked(x, y):
            dice = libtcod.random_get_int(0, 0, 100)
            if dice <70:#healing potion
                item_component = Item(use_function =cast_heal)
                item = Object(x, y, '!', 'Healing potion', libtcod.violet,item = item_component)
            elif dice < 70+10:
                item_component = Item(use_function=cast_confuse)
                item = Object(x, y, '#', 'Scroll of confuse', libtcod.light_green, item = item_component)
            elif dice <70+10+10:
                #fireball spell
                item_component = Item(use_function=cast_fireball)
                item = Object(x, y, '#', 'Scroll of fireball', libtcod.green, item=item_component)
            else:
                #lightning bolt
                item_component = Item(use_function = cast_lightning)
                item = Object(x, y, '#', 'Scroll of lighting bolt', libtcod.green, item = item_component)

            objects.append(item)
            item.send_to_back() #item apear below monsters

def closest_monster(max_range):
    closest_monster = None
    closest_dist = max_range +1

    for object in objects:
        if object.fighter and not object == player and libtcod.map_is_in_fov(fov_map, object.x, object.y):
            dist = player.distance_to(object)
            if dist < closest_dist:
                closest_enemy = object
                closest_dist = dist
    return closest_enemy

def is_blocked(x,y):
    if map[x][y].blocked:
        return True

    for object in objects:
        if object.blocks and object.x ==x and object.y == y:
            return True
    return False

def player_move_or_attack(dx, dy):
    global fov_recompute

    x = player.x + dx
    y = player.y + dy

    target = None

    for object in objects:
        if object.fighter and object.x == x and object.y == y:
            target = object
            break

    if target is not None:
        player.fighter.attack(target)
    else:
        player.move(dx,dy)
        fov_recompute = True

def player_death(player):
    #ya nerd, you died!
    global game_state
    message( 'Ya died nerd', libtcod.red)
    game_state = 'dead'

    player.char = '%'
    player.color = libtcod.dark_red

def monster_death(monster):

    message( monster.name.capitalize() + ' is dead!', libtcod.green)
    monster.char = '%'
    monster.color = libtcod.dark_red
    monster.blocks = False
    monster.fighter = None
    monster.ai = None
    monster.name = monster.name + '`s corpse'
    monster.send_to_back()

def render_bar(x, y, total_width, name, value, maximum, bar_color, back_color):
    bar_width = int(float(value)/maximum * total_width)
    
    #render bar background
    libtcod.console_set_default_background(panel, back_color)
    libtcod.console_rect(panel, x, y, total_width, 1, False, libtcod.BKGND_SCREEN)

    #render bar on top
    libtcod.console_set_default_background(panel, bar_color)
    if bar_width > 0:
        libtcod.console_rect(panel, x, y, bar_width, 1, False, libtcod.BKGND_SCREEN)
    #text for the bars
    libtcod.console_set_default_foreground(panel, libtcod.white)
    libtcod.console_print_ex(panel, x +total_width/2, y, libtcod.BKGND_NONE, libtcod.CENTER, name + ': ' + str(value) + '/' + str(maximum))

def message(new_msg, color = libtcod.white):
    global game_msgs
    new_msg_lines = textwrap.wrap(new_msg, MSG_WIDTH)
    
    for line in new_msg_lines:
        if len(game_msgs) ==MSG_HEIGHT:
            del game_msgs[0]

        game_msgs.append((line, color))

def menu(header, options, width):
    if len(options) > 26:raise ValueError('Cannot have a menu with more than 26 options')

    #calculate the hight of the header
    header_height = libtcod.console_get_height_rect(con, 0, 0, width, SCREEN_HEIGHT, header)
    height = len(options) + header_height
    
    #menu window
    window = libtcod.console_new(width, height)

    #print header, auto wraped
    libtcod.console_set_default_foreground(window, libtcod.white)
    libtcod.console_print_rect_ex(window, 0, 0, width, height, libtcod.BKGND_NONE, libtcod.LEFT, header)
    #menu options
    y = header_height
    letter_index = ord('a')
    for option_text in options:
        text = '(' + chr(letter_index) + ')' + option_text
        libtcod.console_print_ex(window, 0, y, libtcod.BKGND_NONE, libtcod.LEFT, text)
        y +=1
        letter_index +=1

    #blit to screen
    x = SCREEN_WIDTH/2 - width/2
    y = SCREEN_HEIGHT/2 - height/2
    libtcod.console_blit(window, 0, 0, width, height, 0, x, y, 1.0, 0.7)

    #hold window open until keypress
    libtcod.console_flush()
    key = libtcod.console_wait_for_keypress(True)

    #convert the ASCII code to an index; if it corresponds to an option, return it
    index = key.c -ord('a')
    if index >= 0 and index <len(options): return index
    return None

def inventory_menu(header):
    if len(inventory) ==0:
        options = ['Invetory is empty, Go find some loot moron']
    else:
        options = [item.name for item in inventory]

    index = menu(header,options, INVENTORY_WIDTH)

    if index is None or len(inventory) ==0: return None
    return inventory[index].item

def cast_heal():
    #heal the player
    if player.fighter.hp == player.fighter.max_hp:
        message("you're already full heal moron!", libtcod.red)
        return 'cancelled'
    
    message('Your wounds feel less hurty!',libtcod.light_violet)
    player.fighter.heal(HEAL_AMOUNT)

def cast_lightning():
    LIGHTNING_DAMAGE = 20
    LIGHTNING_RANGE = 5

    monster = closest_monster(LIGHTNING_RANGE)
    if monster is None: 
        message('You need people to zap. move closer to those Trolls over there', libtcod.red)
        return 'cancelled'

    #else, lighting
    message('A lightning bolt strikes the '+ monster.name+' with a loud thunder! The damage is ' + str(LIGHTNING_DAMAGE) + ' hit pints.', libtcod.light_blue)
    monster.fighter.take_damage(LIGHTNING_DAMAGE)
    message('was that really necessary?',libtcod.light_blue)

def cast_confuse():
    monster = closest_monster(CONFUSE_RANGE)
    if monster is None:
        message('You need people to confuse, try talking to yourself', libtcod.red)
        return 'cancelled'

    old_ai = monster.ai
    monster.ai = ConfusedMonster(old_ai)
    monster.ai.owner = monster
    message('The eyes of the ' + monster.name + ' look vacent, as he starts to stumble around!', libtcod.light_green)

def cast_fireball():
    message('left click a target tile for teh fireball. Or right click to cancel.', libtcod.light_cyan)
    (x, y) = target_tile()
    if x is None: return 'cancelled'

    message('The fireball explodes, burning everthing within '+ str(FIREBALL_RADIUS) + ' tiles!', libtcod.orange)

    for obj in objects:
        if obj.distance(x, y) <= FIREBALL_RADIUS and obj.fighter:
            message('The ' + obj.name + ' gets burned for ' + str(FIREBALL_DAMAGE) + ' damage!', libtcod.orange)
            obj.fighter.take_damage(FIREBALL_DAMAGE)

#console initialization
libtcod.console_set_custom_font('arial10x10.png',libtcod.FONT_TYPE_GREYSCALE | libtcod.FONT_LAYOUT_TCOD)
#screen initialization root is view, con is model, panel is Gui stuff
libtcod.console_init_root(SCREEN_WIDTH,SCREEN_HEIGHT, 'Python libtcodpy Tutorial',False)
con = libtcod.console_new(SCREEN_WIDTH,SCREEN_HEIGHT)
panel = libtcod.console_new(SCREEN_WIDTH, PANEL_HEIGHT)


libtcod.sys_set_fps(LIMIT_FPS)


def new_game():
    global player, inventory, game_msgs, game_state
    #Object initialization
    player_fighter_component = Fighter(hp=30, defense=2, power=5, death_function = player_death)
    player = Object(SCREEN_WIDTH/2,SCREEN_HEIGHT/2,'@','player',libtcod.white,blocks = True,fighter=player_fighter_component, speed=PLAYER_SPEED)
    objects = [player]
    #game state set 
    game_state = 'playing'


    # generates the map(NOT DRAWN)
    make_map()

    inventory = []
    game_msgs = []

    #opening message
    message('Welcome, to Ethans RL.  I bet you dont survive the floor', libtcod.red)

    initialize_fov()


def next_level():
    #advance to the enxt level
    message('You take a moment to rest and recover your strength', libtcod.light_violet)
    player.fighter.heal(player.fighter.max_hp/2) #half health heal

    message('You descend ever deeper...', libtcod.red)
    make_map()
    initialize_fov()
    

def initialize_fov():
    global fov_recompute, fov_map
    #fov mapping
    fov_recompute = True
    libtcod.console_clear(con)
    fov_map = libtcod.map_new(MAP_WIDTH, MAP_HEIGHT)

    for y in range(MAP_HEIGHT):
        for x in range(MAP_WIDTH):
            libtcod.map_set_properties(fov_map, x, y, not map[x][y].block_sight, not map[x][y].blocked)

def save_game(): 
    global map, objects, player, inventory, game_msgs, game_state
    file = shelve.open('savegame', 'n')
    file['map']= map
    file['objects'] = objects
    file['player_index'] = objects.index(player)
    file['inventory'] = inventory
    file['game_msgs'] = game_msgs
    file['game_state'] = game_state
    file.close()

def load_game():
    global map, objects, player, inventory, game_msgs, game_state

    file.shelve.open('savegame', 'r')
    map = file['map']
    objects = file['objects']
    player = objects[file['player_index']]
    inventory = file['inventory']
    game_msgs = file['game_msgs']
    game_state = file['game_state']

    file.close()

    initialize_fov()

def play_game():
    global key, mouse 

    player_action = None
    
    #configure mouse keyboard
    mouse = libtcod.Mouse()
    key = libtcod.Key()

    #game loop
    while not libtcod.console_is_window_closed():
        libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS| libtcod.EVENT_MOUSE, key, mouse)
        render_all()
    
        libtcod.console_flush()    

        for object in objects:
            object.clear()

        player_action = handle_keys()
        if game_state == 'playing':
            for object in objects:
                if object.ai:
                    if object.wait >0: #dont take a turn if still waiting
                        object.wait -=1
                    else:
                        object.ai.take_turn()

        if player_action == 'exit':
            break
def msgbox(text, width=50):
    menu(text, [], width)

def main_menu():
    key = libtcod.Key()    
    img = libtcod.image_load('menu_background.png')
    while not libtcod.console_is_window_closed():
        libtcod.image_blit_2x(img, 0, 0, 0)

        
        #show the games menu and title and credits
        libtcod.console_set_default_foreground(0, libtcod.light_yellow)
        libtcod.console_print_ex(0, SCREEN_WIDTH/2, SCREEN_HEIGHT/2-4, libtcod.BKGND_NONE, libtcod.CENTER, "The Quest to be Ethan")
        libtcod.console_print_ex(0, SCREEN_WIDTH/2, SCREEN_HEIGHT-2, libtcod.BKGND_NONE, libtcod.CENTER, 'By Ethan')
        choice = menu('',['Play a new game','Continue last game', 'Quit'], 24)
        
        if key.vk == libtcod.KEY_ENTER and key.lalt:
            libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())

        if choice == 0: #new game
            new_game()
            play_game()
        elif choice ==1:
            try:
                load_game()
            except:
                msgbox('\nNo saved game to load\n', 24)
                continue
            play_game()
        elif choice ==2: #quit
            save_game()
            break

main_menu()
