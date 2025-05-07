import json

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Permite accesul la API din React
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://10.65.10.164:3000"],  # Permite acces doar de la frontend-ul React
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Gestionarea conexiunilor WebSocket
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(json.dumps({"message": message}))


manager = ConnectionManager()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            print(f"Message received: {data}")

            try:
                # Process the move and update the board
                move_data = json.loads(data)
                move = move_data.get("move")
                if move:
                    make_move(MoveRequest(move=move))  # Update the board state

                # Broadcast the updated board to all clients
                await manager.broadcast(json.dumps({
                    "board": board,
                    "current_turn": current_turn,
                    "game_over": game_over,
                    "winner": winner
                }))
            except Exception as e:
                print(f"Error processing move: {e}")
                await websocket.send_text(json.dumps({"error": "Invalid move or server error"}))
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print("Client disconnected")
# Tabla de șah inițială
board = [
    ["r", "n", "b", "q", "k", "b", "n", "r"],
    ["p", "p", "p", "p", "p", "p", "p", "p"],
    [".", ".", ".", ".", ".", ".", ".", "."],
    [".", ".", ".", ".", ".", ".", ".", "."],
    [".", ".", ".", ".", ".", ".", ".", "."],
    [".", ".", ".", ".", ".", ".", ".", "."],
    ["P", "P", "P", "P", "P", "P", "P", "P"],
    ["R", "N", "B", "Q", "K", "B", "N", "R"],
]


def is_valid_move(move: str):
    print(f"\n=== Verificare mutare: {move} ===")

    # Extract positions and validate input
    if len(move) != 5:
        print("❌ Eroare: Mutarea nu are lungimea corectă!")
        return False

    start_pos = move[1:3]
    end_pos = move[3:]
    start_col, start_row = ord(start_pos[0].upper()) - 65, 8 - int(start_pos[1])
    end_col, end_row = ord(end_pos[0].upper()) - 65, 8 - int(end_pos[1])

    if not (0 <= start_row < 8 and 0 <= start_col < 8 and 0 <= end_row < 8 and 0 <= end_col < 8):
        print("❌ Eroare: Poziția este în afara tablei!")
        return False

    piece_on_board = board[start_row][start_col]
    target_piece = board[end_row][end_col]

    # Ensure the piece exists at the start position
    if piece_on_board == ".":
        print("❌ Eroare: Nu există nicio piesă pe poziția de start!")
        return False

    # Ensure the target is not a friendly piece
    if (piece_on_board.isupper() and target_piece.isupper()) or (piece_on_board.islower() and target_piece.islower()):
        print("❌ Eroare: Nu poți captura o piesă prietenă!")
        return False

    # Check if the target piece is a pawn
    if target_piece.lower() == 'p':
        print("🔍 Captură pion - fără explozie.")
        return True  # Valid move without explosion

    # Check if the move would cause an explosion that kills the current player's king
    if target_piece != ".":
        temp_board = [row[:] for row in board]  # Create a temporary board
        temp_board[end_row][end_col] = piece_on_board
        temp_board[start_row][start_col] = "."
        try:
            apply_explosion(end_row, end_col, piece_on_board)
        except HTTPException as e:
            if "your own king" in e.detail:
                print("❌ Mutare invalidă: Explozia ar ucide propriul rege!")
                return False
    # Reguli pentru piese (șah clasic)
    if piece_on_board.lower() == 'p':  # Pion
        if piece_on_board.isupper():  # Alb
            if start_col == end_col and start_row - 2 == end_row and board[end_row][end_col] == "." and \
                    board[start_row - 1][start_col] == "." and start_row == 6:
                print("✅ Mutare validă: Pion alb înainte cu 2")
                return True
            if start_col == end_col and start_row - 1 == end_row and board[end_row][end_col] == ".":
                print("✅ Mutare validă: Pion alb înainte cu 1")
                return True
            if abs(start_col - end_col) == 1 and start_row - 1 == end_row and board[end_row][end_col].islower():
                print("✅ Captură validă: Pion alb")
                return True
        else:  # Negru
            if start_col == end_col and start_row + 2 == end_row and board[end_row][end_col] == "." and board[start_row + 1][start_col] == "." and start_row == 1:
                print("✅ Mutare validă: Pion negru înainte cu 2")
                return True
            if start_col == end_col and start_row + 1 == end_row and board[end_row][end_col] == ".":
                print("✅ Mutare validă: Pion negru înainte cu 1")
                return True
            if abs(start_col - end_col) == 1 and start_row + 1 == end_row and board[end_row][end_col].isupper():
                print("✅ Captură validă: Pion negru")
                return True
    elif piece_on_board.lower() == 'r':  # Tura
        if start_row == end_row:
            for i in range(min(start_col, end_col) + 1, max(start_col, end_col)):
                if board[start_row][i] != ".":
                    print("❌ Eroare: Tura nu poate să sară peste piese!")
                    return False
            print("✅ Mutare validă: Tura pe orizontală")
            return True
        if start_col == end_col:
            for i in range(min(start_row, end_row) + 1, max(start_row, end_row)):
                if board[i][start_col] != ".":
                    print("❌ Eroare: Tura nu poate să sară peste piese!")
                    return False
            print("✅ Mutare validă: Tura pe verticală")
            return True

    elif piece_on_board.lower() == 'n':  # Cal
        if (abs(start_row - end_row) == 2 and abs(start_col - end_col) == 1) or (abs(start_row - end_row) == 1 and abs(start_col - end_col) == 2):
            print("✅ Mutare validă: Cal")
            return True

    elif piece_on_board.lower() == 'b':  # Nebun
        if abs(start_row - end_row) == abs(start_col - end_col):
            step_row = 1 if end_row > start_row else -1
            step_col = 1 if end_col > start_col else -1
            r, c = start_row + step_row, start_col + step_col
            while r != end_row:
                if board[r][c] != ".":
                    print("❌ Eroare: Nebunul nu poate să sară peste piese!")
                    return False
                r += step_row
                c += step_col
            print("✅ Mutare validă: Nebun pe diagonală")
            return True

    elif piece_on_board.lower() == 'q':  # Regina
        if start_row == end_row:  # Horizontal movement
            for i in range(min(start_col, end_col) + 1, max(start_col, end_col)):
                if board[start_row][i] != ".":
                    print("❌ Eroare: Regina nu poate să sară peste piese pe orizontală!")
                    return False
            print("✅ Mutare validă: Regina pe orizontală")
            return True
        elif start_col == end_col:  # Vertical movement
            for i in range(min(start_row, end_row) + 1, max(start_row, end_row)):
                if board[i][start_col] != ".":
                    print("❌ Eroare: Regina nu poate să sară peste piese pe verticală!")
                    return False
            print("✅ Mutare validă: Regina pe verticală")
            return True
        elif abs(start_row - end_row) == abs(start_col - end_col):  # Diagonal movement
            step_row = 1 if end_row > start_row else -1
            step_col = 1 if end_col > start_col else -1
            r, c = start_row + step_row, start_col + step_col
            while r != end_row:
                if board[r][c] != ".":
                    print("❌ Eroare: Regina nu poate să sară peste piese pe diagonală!")
                    return False
                r += step_row
                c += step_col
            print("✅ Mutare validă: Regina pe diagonală")
            return True


    elif piece_on_board.lower() == 'k':  # Regele

        if abs(start_row - end_row) <= 1 and abs(start_col - end_col) <= 1:
            return True

    print("❌ Mutare invalidă!")
    return False  # Dacă niciuna dintre condiții nu este îndeplinită



# Cerere POST pentru a muta piesele
class MoveRequest(BaseModel):
    move: str

# Variabile globale pentru starea jocului
game_over = False
winner = None

def apply_explosion(row, col, moving_piece):
    """Applies the explosion effect at the given position, keeping the moving piece intact."""
    global board, game_over, winner

    if board[row][col].lower() == 'p':
        board[row][col] = moving_piece
        return True

    directions = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
    exploded_positions = []

    for dr, dc in directions:
        r, c = row + dr, col + dc
        if 0 <= r < 8 and 0 <= c < 8:
            exploded_positions.append((r, c))

    for r, c in exploded_positions:
        if board[r][c].lower() == 'k':  # Dacă un rege este capturat
            game_over = True
            winner = "white" if board[r][c].islower() else "black"
        board[r][c] = "."

    board[row][col] = moving_piece
# Variabilă globală pentru a ține evidența rândului curent
current_turn = "white"  # Încep cu albul

@app.post("/move")
def make_move(move_request: MoveRequest):
    global current_turn, game_over, winner

    if game_over:
        raise HTTPException(status_code=400, detail=f"Jocul s-a terminat! Câștigător: {winner}")
    move = move_request.move
    print(f"Mutare primită: {move}")

    # Extract source and target positions
    source = move[1:3]
    target = move[3:]

    start_row, start_col = 8 - int(source[1]), ord(source[0].upper()) - 65
    end_row, end_col = 8 - int(target[1]), ord(target[0].upper()) - 65
    moving_piece = board[start_row][start_col]

    # Verifică dacă piesa aparține jucătorului curent
    if current_turn == "white" and not moving_piece.isupper():
        raise HTTPException(status_code=400, detail="Este rândul pieselor albe!")
    if current_turn == "black" and not moving_piece.islower():
        raise HTTPException(status_code=400, detail="Este rândul pieselor negre!")

    # Verifică dacă mutarea este validă
    if not is_valid_move(move):
        raise HTTPException(status_code=400, detail="Mutare ilegală!")

    # Update the board
    target_piece = board[end_row][end_col]
    if target_piece != "." and moving_piece.lower() != 'p':  # Non-pawn capture
        apply_explosion(end_row, end_col, moving_piece)  # Trigger explosion at the target position
    else:
        # Normal move (no explosion)
        board[end_row][end_col] = moving_piece

    # Clear the starting position
    board[start_row][start_col] = "."

    # Schimbă rândul
    current_turn = "black" if current_turn == "white" else "white"

    print(f"Tabla după mutare: {board}")
    return {"message": f"Mutare efectuată de la {source} la {target}", "board": board, "current_turn": current_turn}
# Endpoint pentru a obține tabla
@app.get("/board")
def get_board():
    return {"board": board, "current_turn": current_turn}


# Resetarea tablei
@app.post("/reset")
def reset_board():
    global board, current_turn
    board = [
        ["r", "n", "b", "q", "k", "b", "n", "r"],
        ["p", "p", "p", "p", "p", "p", "p", "p"],
        [".", ".", ".", ".", ".", ".", ".", "."],
        [".", ".", ".", ".", ".", ".", ".", "."],
        [".", ".", ".", ".", ".", ".", ".", "."],
        [".", ".", ".", ".", ".", ".", ".", "."],
        ["P", "P", "P", "P", "P", "P", "P", "P"],
        ["R", "N", "B", "Q", "K", "B", "N", "R"],
    ]
    current_turn = "white"  # Resetăm tura la alb
    return {"board": board, "current_turn": current_turn}
