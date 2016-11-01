#!/usr/bin/python2
import tcod as libtcod
SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50

MAP_WIDTH = 80
MAP_HEIGHT = 45

ROOM_MAX_SIZE = 10
ROOM_MIN_SIZE = 6
MAX_ROOMS = 30

MAX_ROOM_MONSTERS = 3

LIMIT_FPS = 20

FOV_ALGO = 0
FOV_LIGHT_WALLS = True
TORCH_RADIUS = 10

color_dark_wall = libtcod.Color(10, 10, 100)
color_light_wall = libtcod.Color(130, 11, 50)
color_dark_ground = libtcod.Color(50, 50, 150)
color_light_ground = libtcod.Color(200, 180, 50)

game_state = 'playing'
player_action = None

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
    def __init__(self,x,y,char,name,color,blocks = False):
        self.x = x
        self.y = y
        self.char = char
        self.color = color
        self.name = name
        self.blocks = blocks

    def move(self,dx,dy):
        #move by the given delta's
        if not is_blocked(self.x +dx, self.y +dy):
            self.x += dx
            self.y += dy

    def draw(self):
        #set the color then draw the character that represents this object in its position 
        if libtcod.map_is_in_fov(fov_map, self.x, self.y):
            libtcod.console_set_default_foreground(con,self.color)
            libtcod.console_put_char(con,self.x,self.y,self.char,libtcod.BKGND_NONE)


    def clear(self):
        #erase the character that represents the object
        libtcod.console_put_char(con,self.x,self.y,' ',libtcod.BKGND_NONE)

def handle_keys():
    global fov_recompute
    global playerx, playery
    

    key = libtcod.console_check_for_keypress()
    if key.vk == libtcod.KEY_ENTER and key.lalt:
        #alt enter to full screen
        libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())
    elif key.vk == libtcod.KEY_ESCAPE:
        #escape exits game
        return True 
    if game_state == 'playing'
        #movement keys
        if libtcod.console_is_key_pressed(libtcod.KEY_UP):
            player.move(0,-1)
            fov_recompute = True
        elif libtcod.console_is_key_pressed(libtcod.KEY_DOWN):
            player.move(0,1)
            fov_recompute = True
        elif libtcod.console_is_key_pressed(libtcod.KEY_LEFT):
            player.move(-1,0)
            fov_recompute = True
        elif libtcod.console_is_key_pressed(libtcod.KEY_RIGHT):
            player.move(1,0)
            fov_recompute = True

def make_map():
    global map

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
    #set contents of con to the root console 
    libtcod.console_blit(con,0,0,SCREEN_WIDTH,SCREEN_HEIGHT,0,0,0)

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
        x = libtcod.random_get_int(0, room.x1, room.x2)
        y = libtcod.random_get_int(0, room.y1, room.y2)
        if not is_blocked(x, y):
            choice = libtcod.random_get_int(0,0,100)
            if choice< 40: #80% chance of orc
                #ORC
                monster = Object(x, y, 'o', 'orc', libtcod.desaturated_green, blocks = True)
            elif choice ==41: #1% chance of Alec
                monster = Object(x, y, 'A', 'Alec', libtcod.orange, blocks = True)
            elif choice > 41: 
                monster = Object(x, y, 'J', 'Jacobi', libtcod.light_purple, blocks = True)
            else:
                #TROLL
                monster = Object(x, y, 'T', 'Troll', libtcod.darker_green, blocks = True)
            objects.append(monster)

def is_blocked(x,y):
    if map[x][y].blocked:
        return True

    for object in objects:
        if object.blocks and object.x ==x and object.y == y:
            return True
    return False

#console initialization
libtcod.console_set_custom_font('arial10x10.png',libtcod.FONT_TYPE_GREYSCALE | libtcod.FONT_LAYOUT_TCOD)

libtcod.console_init_root(SCREEN_WIDTH,SCREEN_HEIGHT, 'Python libtcodpy Tutorial',False)
con = libtcod.console_new(SCREEN_WIDTH,SCREEN_HEIGHT)

libtcod.sys_set_fps(LIMIT_FPS)



#Object initialization
player = Object(SCREEN_WIDTH/2,SCREEN_HEIGHT/2,'@','player',libtcod.white,blocks = True)
objects = [player]
# generates the map(NOT DRAWN)
make_map()

#fov mapping
fov_map = libtcod.map_new(MAP_WIDTH, MAP_HEIGHT)
for y in range(MAP_HEIGHT):
    for x in range(MAP_WIDTH):
        libtcod.map_set_properties(fov_map, x, y, not map[x][y].block_sight, not map[x][y].blocked)

fov_recompute = True

#game loop
while not libtcod.console_is_window_closed():
    render_all()
    
    libtcod.console_flush()    

    for object in objects:
        object.clear()

    exit = handle_keys()
    if exit:
        break
