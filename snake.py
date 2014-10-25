#!/usr/bin/env python
from __future__ import print_function, division
import random
import time
import os
import sys
import copy
from collections import namedtuple
import curses

stdscr = curses.initscr()
curses.noecho()
curses.cbreak()
stdscr.keypad(1)
win = curses.newwin(50, 120, 0, 0)
win.nodelay(1)

Point = namedtuple('Point', 'ud lr')
Velocity = namedtuple('Velocity', 'ud lr')


class BangError(BaseException):
    pass


class Snake(object):

    def __init__(self, start_position=[Point(ud=0, lr=0)],
                 velocities=[Velocity(ud=-1, lr=0)], sym="@"):
        self.positions = start_position
        self.velocities = velocities * len(start_position)

        self.directions = dict(left=Velocity(ud=0, lr=-1),
                               right=Velocity(ud=0, lr=1),
                               up=Velocity(ud=-1, lr=0),
                               down=Velocity(ud=1, lr=0))
        self.bound_ud = None
        self.bound_lr = None
        self.sym = sym

    @staticmethod
    def sum_of_two_pairs(a, b):
        return a[0] + b[0], a[1] + b[1]

    def change_velocity(self, direction):
        new_velocity = self.directions[direction]
        # if direction is opposite to current cannot change the velocity
        if self.sum_of_two_pairs(self.velocities[0], new_velocity) == (0, 0):
            return
        else:
            self.velocities[0] = new_velocity

    def correct_bounds(self, p_ud, p_lr):
            new_p_ud = p_ud
            new_p_lr = p_lr
            if p_ud < 0:
                new_p_ud = self.bound_ud-1
            if self.bound_ud-1 < p_ud:
                new_p_ud = 0
            if p_lr < 0:
                new_p_lr = self.bound_lr-1
            if self.bound_lr-1 < p_lr:
                new_p_lr = 0
            return Point(new_p_ud, new_p_lr)

    def update_position(self):
        new_velocities = []
        for i, part in enumerate(self.positions):
            if i == 0:
                new_velocities.append(self.velocities[i])
            else:
                y, x = self.correct_bounds(
                    *self.sum_of_two_pairs(part, self.velocities[i]))
                if Point(y, x) in self.positions:
                    new_velocities.append(self.velocities[i-1])
                else:
                    new_velocities.append(self.velocities[i])
        unsafe_positions = map(lambda(x, y): self.sum_of_two_pairs(x, y),
                               zip(self.positions, self.velocities))
        self.velocities = new_velocities[:]
        self.positions = map(lambda(x, y): self.correct_bounds(x, y),
                             unsafe_positions)
        if len(self.positions) != len(set(self.positions)) or\
                len(self.positions) == 0:
            raise BangError

    def add_part(self):
        y, x = self.positions[-1]
        y -= self.velocities[-1].ud
        x -= self.velocities[-1].lr
        self.positions.append(self.correct_bounds(y, x))
        self.velocities.append(self.velocities[-1])

    def remove_part(self, n=1):
        try:
            for _ in range(n):
                self.positions.pop()
                self.velocities.pop()
        except IndexError:
            raise BangError


class Game(object):

    def __init__(self, height=15, width=40, update_rate=1/6.5):
        self.height = height
        self.width = width
        self.empty_field =\
            [[' ' for i in xrange(width)] for j in xrange(height)]
        self.filled_field = []
        self.update_rate = update_rate

        self.snake = None

        self.food_probability = .06
        self.food_position = []
        self.food_expires = []
        self.food_sym = "%"
        self.food_min_life = 80
        self.food_max_life = 110
        self.food_score = 300

        self.trap_probability = .04
        self.trap_position = []
        self.trap_expires = []
        self.trap_sym = "^"
        self.trap_min_life = 250
        self.trap_max_life = 300
        self.trap_score = 250
        self.trap_damage = 8

        self.score = 0
        self.text = {

            "bottom": (
                "Hello reptile! Hunt little bunnies(%),\n"
                "be careful with huntsman's traps(^) and try to don't\n"
                "eat yourself. Thanks for you are a super-snake, you can\n"
                "slow down or speed up the stream of time.\n"
                "But it looks like recently you have damaged your brain\n"
                "and you have a bit slow response. Have a fun:)\n"

                "\nh(a) - left, l(d) - right, j(s) - down, k(w) - up;\n"
                "q - slow down, e - speed up;\n"
                # "r - increase snake, t - decrease snake\n"
                "p - pause; ctrl-c - exit;\n"),
            "exit": "Thanks for the game! Press <Enter> to exit.\n",
            "lose": "You lose!!! Press <Enter> to exit.\n",
            "score": "\nYour score is {}.\n"
        }

    def add_snake(self, snake):
        self.snake = snake
        self.snake.bound_ud = self.height
        self.snake.bound_lr = self.width
        self.snake.sym = "0"

    def add_borders(self, field, left=1, right=1, top=1, bottom=1,
                    sym_lr='|', sym_tb='-'):
        height = len(field)
        width = len(field[0])
        field_with_borders = []
        for i in range(height + top + bottom):
            if i < top or top + height <= i:
                row = [sym_tb] * (left + width + right)
            else:
                row = [sym_lr] * left + field[i-top] + [sym_lr] * right
            field_with_borders.append(row)
        return field_with_borders

    def substitute(self):
        field_to_fill = copy.deepcopy(self.empty_field)
        for p in self.snake.positions:
            field_to_fill[p.ud][p.lr] = self.snake.sym
        for p in self.food_position:
            field_to_fill[p.ud][p.lr] = self.food_sym
        for p in self.trap_position:
            field_to_fill[p.ud][p.lr] = self.trap_sym
        self.filled_field = self.add_borders(field_to_fill)

    def render(self, field):
        self.substitute()
        for line in self.filled_field:
            win.addstr(''.join(line) + '\n')
        win.addstr(self.text["bottom"])
        win.addstr(self.text["score"].format(self.score))
        win.refresh()

    def clear_screen(self):
        os.system('clear')

    def add_food(self):
        y = random.randint(0, self.height-1)
        x = random.randint(0, self.width-1)
        t = random.randint(self.food_min_life, self.food_max_life)
        self.food_position.append(Point(y, x))
        self.food_expires.append(t)

    def delete_food(self, i):
        self.food_position.pop(i)
        self.food_expires.pop(i)

    def add_trap(self):
        y = random.randint(0, self.height-1)
        x = random.randint(0, self.width-1)
        t = random.randint(self.trap_min_life, self.trap_max_life)
        self.trap_position.append(Point(y, x))
        self.trap_expires.append(t)

    def delete_trap(self, i):
        self.trap_position.pop(i)
        self.trap_expires.pop(i)

    def update(self):
        win.erase()
        self.snake.update_position()
        self.food_expires = map(lambda x: x-1, self.food_expires)
        self.trap_expires = map(lambda x: x-1, self.trap_expires)
        if not all(self.food_expires):
            self.food_position = [v for i, v in enumerate(self.food_position)
                                  if self.food_expires[i] > 0]
            self.food_expires = [v for i, v in enumerate(self.food_expires)
                                 if self.food_expires[i] > 0]
        if random.random() < self.food_probability:
            self.add_food()
        for i, food_point in enumerate(self.food_position):
            if food_point in self.snake.positions:
                self.snake.add_part()
                self.delete_food(i)
                self.score += self.food_score

        if not all(self.trap_expires):
            self.trap_position = [v for i, v in enumerate(self.trap_position)
                                  if self.trap_expires[i] > 0]
            self.trap_expires = [v for i, v in enumerate(self.trap_expires)
                                 if self.trap_expires[i] > 0]
        if random.random() < self.trap_probability:
            self.add_trap()
        for i, trap_point in enumerate(self.trap_position):
            if trap_point in self.snake.positions:
                self.snake.remove_part(self.trap_damage)
                self.delete_trap(i)
                self.score -= self.trap_damage * self.trap_score

        self.render(self.filled_field)

    def start(self):
        while True:
            try:
                curses.napms(int(self.update_rate*1000))
                self.update()
                c = win.getch()
                direction = None
                if c in (ord("h"), ord("a"), curses.KEY_LEFT): # c == ord("h") or c == ord("a"):
                    direction = "left"
                elif c in (ord("j"), ord("s"), curses.KEY_DOWN):
                    direction = "down"
                elif c in (ord("k"), ord("w")):
                    direction = "up"
                elif c in (ord("l"), ord("d")):
                    direction = "right"

                elif c == ord("q"):
                    self.update_rate *= 1.1
                elif c == ord("e"):
                    self.update_rate /= 1.1

                elif c == ord("r"):
                    self.snake.add_part()
                elif c == ord("t"):
                    self.snake.remove_part()

                elif c == ord("p"):
                    win.addstr("Pause...")
                    while True:
                        ch = win.getch()
                        if ch == ord("p"):
                            break

                if direction:
                    self.snake.change_velocity(direction)
            except KeyboardInterrupt:
                win.addstr(self.text["exit"])
                win.refresh()
                break
            except BangError:
                self.render(self.filled_field)
                win.addstr(self.text["lose"].format(self.score))
                win.refresh()
                break
        win.nodelay(0)
        c = win.getch()
        if c != curses.KEY_ENTER:
            c = win.getch()
        curses.endwin()
        sys.exit(0)


def main():
    game = Game()
    snake = Snake(start_position=[Point(game.height//2, game.width//2),
                                  Point(game.height//2 + 1, game.width//2),
                                  Point(game.height//2 + 2, game.width//2),
                                  ])
    game.add_snake(snake)
    game.start()


if __name__ == '__main__':
    main()
