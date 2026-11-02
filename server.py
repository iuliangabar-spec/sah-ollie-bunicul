import os, secrets, time
from threading import Lock
import chess
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title='Sah cu Ollie si Bunicul')
rooms = {}
lock = Lock()

class JoinRequest(BaseModel):
    code: str

class MoveRequest(BaseModel):
    code: str
    token: str
    uci: str

def get_room(code):
    room = rooms.get(code)
    if room is None:
        raise HTTPException(404, 'Partida nu exista')
    return room

def state(room, token=None):
    board = room['board']
    return {'fen': board.fen(), 'turn': 'white' if board.turn else 'black',
            'moves': [m.uci() for m in board.move_stack],
            'is_game_over': board.is_game_over(claim_draw=True),
            'result': board.result(claim_draw=True) if board.is_game_over(claim_draw=True) else None,
            'players': len(room['tokens']),
            'your_color': room['tokens'].get(token) if token else None}

@app.get('/')
def home():
    return {'status': 'online', 'game': 'Sah cu Ollie si Bunicul'}

@app.post('/create')
def create():
    with lock:
        code = ''.join(str(secrets.randbelow(10)) for _ in range(6))
        while code in rooms:
            code = ''.join(str(secrets.randbelow(10)) for _ in range(6))
        token = secrets.token_urlsafe(24)
        rooms[code] = {'board': chess.Board(), 'tokens': {token: 'white'}, 'created': time.time()}
        return {'code': code, 'token': token, 'color': 'white', 'state': state(rooms[code], token)}

@app.post('/join')
def join(req: JoinRequest):
    with lock:
        room = get_room(req.code)
        if len(room['tokens']) >= 2:
            raise HTTPException(409, 'Partida are deja doi jucatori')
        token = secrets.token_urlsafe(24)
        room['tokens'][token] = 'black'
        return {'code': req.code, 'token': token, 'color': 'black', 'state': state(room, token)}

@app.get('/state/{code}')
def get_state(code: str):
    with lock:
        return state(get_room(code))

@app.post('/move')
def move(req: MoveRequest):
    with lock:
        room = get_room(req.code)
        color = room['tokens'].get(req.token)
        if color is None:
            raise HTTPException(403, 'Jucator neautorizat')
        board = room['board']
        if board.is_game_over(claim_draw=True):
            raise HTTPException(409, 'Partida s-a terminat')
        if color != ('white' if board.turn else 'black'):
            raise HTTPException(409, 'Nu este randul tau')
        try:
            chess_move = chess.Move.from_uci(req.uci)
        except ValueError:
            raise HTTPException(400, 'Mutare invalida')
        if chess_move not in board.legal_moves:
            raise HTTPException(400, 'Mutare ilegala')
        board.push(chess_move)
        return state(room, req.token)
