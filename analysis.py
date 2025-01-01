import chess
import chess.engine
import chess.polyglot
import chess.pgn
import argparse
import math
import json

MATE_THRES = 32000
BOOK_PATH = "Titans.bin"

# Coefficients for the elo quadratic
A = -10.511
B = 2080 # 2083.7 (generated - too high)
C = -99663

class AnalyzedMove:
    def __init__(self,
                score: int, 
                book_mv : bool,
                best: bool,
                turn : int,
                forced : bool,
                move : chess.Move,
                comment : str):
        self.score = score
        self.book = book_mv
        self.best = best
        self.turn = turn
        self.forced = forced
        self.move = move
        self.comment = comment


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument('-p', '--pgn', type=str, dest="pgn")
    parser.add_argument('-e', '--engine', type=str, dest="engine")
    parser.add_argument('-d', '--depth', type=int, dest="depth", default=18)

    return parser.parse_args()

args = parse_args()


def printProgressBar (iteration, total, prefix = '', suffix = '', decimals = 1, length = 30, fill = '█', printEnd = "\r"):
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filledLength = int(length * iteration // total)
    bar = fill * filledLength + '-' * (length - filledLength)
    print(f'\r{prefix} |{bar}| {percent}% {suffix}', end = printEnd)
    # Print New Line on Complete
    if iteration == total: 
        print()

# Accuracy logic by lichess (https://lichess.org/page/accuracy)
def get_accuracy_of_move(win_b, win_a):
    return 103.1668 * math.exp(-0.04354 * ((win_b) - (win_a))) - 3.1669

def get_accuracy_of_cp(a):
    return 103.1668 * math.exp(-0.04354 * a) - 3.1669

def calculate_wp(centipawns):
    return 50 + 50 * (2 / (1 + math.exp(-0.00368208 * centipawns)) - 1)

def get_model_elo(acc):
    return A * (acc ** 2) + B * acc + C

def apply_elo_model(acc_w, acc_b):
    a_acc = (acc_w + acc_b) / 2
    
    x = max(get_model_elo(a_acc), 100)

    # get our white/black bound elo
    w = max(get_model_elo(acc_w), 100)
    b = max(get_model_elo(acc_b), 100)
    
    w += x
    w /= 2
    
    b += x
    b /= 2
    
    print(f"White Performance: {round(w)}\nBlack Performance: {round(b)}")


def analyze(pgn):
    game               = chess.pgn.read_game(pgn)
    engine             = chess.engine.SimpleEngine.popen_uci(args.engine)
    game_annot         = chess.pgn.Game()
    game_annot.headers = game.headers
    opening_book       = chess.polyglot.open_reader(BOOK_PATH)
    analyzed_moves     = []
    board              = game.board()

    # Analyze all the moves with the engine
    next_best_move = None
    in_book = True
    for move in game.mainline():
        turn = board.turn

        book = False
        if in_book:
            for i in opening_book.find_all(board):
                if i.move == move.move:
                    book = True
                    break
            if not book:
                in_book = False

        forced = len(list(board.legal_moves)) == 1 # A move is "forced" when there is only one possible move

        board.push(move.move) # Step to the next board position
        
        if board.is_checkmate():
            analyzed_moves.append(AnalyzedMove(
                score=0, 
                book_mv=book,
                best=True,
                turn=turn,
                forced=forced,
                move=move.move,
                comment = move.comment
            ))
            break
        
        # Get the engine analysis of the current position
        step = engine.play(board, chess.engine.Limit(depth=args.depth), info=chess.engine.Info.ALL)
        score = step.info["score"].white().score(mate_score=MATE_THRES)

        printProgressBar(len(analyzed_moves), len(list(game.mainline_moves())), suffix=f"{move.move} - {(next_best_move if next_best_move is not None else None)}   ")

        best = next_best_move == move.move
        next_best_move = step.move
        
        analyzed_moves.append(AnalyzedMove(
            score=score, 
            book_mv=book, 
            best=best, 
            turn=turn,
            forced=forced,
            move=move.move,
            comment = move.comment
        ))
    
    # set progress bar to 100
    printProgressBar(1, 1, suffix="             ")
    
    # now assign comments to all of the moves
    previous_score = 0
    winchance_loss = [0, 0]
    centpawn_n = [0, 0]
    accuracy = [[], []]
    main_node = game_annot.add_variation(analyzed_moves[0].move)
    final_sq = chess.square_name(analyzed_moves[0].move.to_square)
    main_node.comment = f"{analyzed_moves[0].comment}  [%c_effect {final_sq};square;{final_sq};type;Book;persistent;true]"
    index = 0
    
    for analyzed_move in analyzed_moves[1:]:
        final_sq = chess.square_name(analyzed_move.move.to_square)
        main_node = main_node.add_main_variation(analyzed_move.move)

        if analyzed_move.book:
            main_node.comment = f"{analyzed_move.comment} [%c_effect {final_sq};square;{final_sq};type;Book;persistent;true]"
            continue
        elif analyzed_move.forced:
            main_node.comment = f"{analyzed_move.comment} [%c_effect {final_sq};square;{final_sq};type;Forced;persistent;true]"
            continue
        
        # get the accuracy of the move
        if analyzed_move.best or round(previous_score, 2) == round(analyzed_move.score, 2):
            analyzed_move.best = True # update this if the move was equal to the best move
            acc = 100
        elif analyzed_move.turn:
            acc = get_accuracy_of_move(calculate_wp(previous_score), calculate_wp(min(analyzed_move.score, previous_score))) 
        else:
            acc = get_accuracy_of_move(calculate_wp(-previous_score), calculate_wp(-max(analyzed_move.score, previous_score)))

        if analyzed_move.best:
            centpawn_n[analyzed_move.turn] += 1
        else:
            winchance_loss[analyzed_move.turn] += calculate_wp(max((previous_score - analyzed_move.score) if analyzed_move.turn else -(previous_score - analyzed_move.score), 0)) - 50
            centpawn_n[analyzed_move.turn]     += 1
        
        accuracy[analyzed_move.turn].append(acc)

        had_improvement_opportunity = abs(analyzed_moves[index - 1].score - analyzed_move.score) > 50

        if analyzed_move.best:
            # check special case (aka great move)
            if index > 2: 
                if abs(analyzed_moves[index - 2].score - analyzed_moves[index - 1].score) > 150:
                    main_node.comment = f"{analyzed_move.comment} [%c_effect {final_sq};square;{final_sq};type;GreatFind;persistent;true]"
                else:
                    main_node.comment = f"{analyzed_move.comment} [%c_effect {final_sq};square;{final_sq};type;BestMove;persistent;true]"
            else:
                main_node.comment = f"{analyzed_move.comment} [%c_effect {final_sq};square;{final_sq};type;BestMove;persistent;true]"
        elif acc > 92:
            main_node.comment = f"{analyzed_move.comment} [%c_effect {final_sq};square;{final_sq};type;Excellent;persistent;true]"
        elif acc > 80:
            main_node.comment = f"{analyzed_move.comment} [%c_effect {final_sq};square;{final_sq};type;Good;persistent;true]"
        elif acc > 70:
            main_node.comment = f"{analyzed_move.comment} [%c_effect {final_sq};square;{final_sq};type;Inaccuracy;persistent;true]"
        elif acc > 20:
            if index > 3 and abs(analyzed_moves[index - 2].score - analyzed_move.score) < 50 and had_improvement_opportunity:
                main_node.comment = f"{analyzed_move.comment} [%c_effect {final_sq};square;{final_sq};type;Miss;persistent;true]"
            else:
                main_node.comment = f"{analyzed_move.comment} [%c_effect {final_sq};square;{final_sq};type;Mistake;persistent;true]"
        else:
            if index > 3 and abs(analyzed_moves[index - 2].score - analyzed_move.score) < 50 and had_improvement_opportunity:
                main_node.comment = f"{analyzed_move.comment} [%c_effect {final_sq};square;{final_sq};type;Miss;persistent;true]"
            else:
                main_node.comment = f"{analyzed_move.comment} [%c_effect {final_sq};square;{final_sq};type;Blunder;persistent;true]"

        previous_score = analyzed_move.score
        index += 1
    
    # average centipawn loss
    winchance_loss[0] /= centpawn_n[0]
    winchance_loss[1] /= centpawn_n[1]
    
    # average accuracy values
    b_acc, w_acc = 0, 0
    for i in accuracy[1]: w_acc += i
    for i in accuracy[0]: b_acc += i
    b_acc /= len(accuracy[0])
    w_acc /= len(accuracy[1])

    print(f"\nWhite Accuracy: {round(get_accuracy_of_cp((winchance_loss[1])), 1)}\nBlack Accuracy: {round(get_accuracy_of_cp((winchance_loss[0])), 1)}")
    print(f"White Winchance Loss: {round(winchance_loss[1])}\nBlack Winchance Loss: {round(winchance_loss[0])}")

    # This is the SGP model
    apply_elo_model(get_accuracy_of_cp((winchance_loss[1])), get_accuracy_of_cp((winchance_loss[0])))

    cleaned_name = args.pgn.replace(".pgn", "")
    print(game_annot, file=open(f"{cleaned_name}_analyzed.pgn", "w"), end="\n\n")
    engine.close()


if __name__ == "__main__":
    analyze(open(args.pgn))