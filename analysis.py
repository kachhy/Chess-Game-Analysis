import chess
import chess.engine
import chess.polyglot
import chess.pgn
import argparse
import math


MATE_THRES = 32000
BOOK_PATH = "Titans.bin"


class AnalyzedMove:
    def __init__(self,
                score: int, 
                book : bool,
                best: bool,
                turn : int,
                forced : bool,
                move : chess.Move):
        self.score = score
        self.book = book
        self.best = best
        self.turn = turn
        self.forced = forced
        self.move = move


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument('-p', '--pgn', type=str, dest="pgn")
    parser.add_argument('-e', '--engine', type=str, dest="engine")
    parser.add_argument('-d', '--depth', type=int, dest="depth", default=18)

    return parser.parse_args()


args = parse_args()

# name of the analysis engine
ENGINE_PATH = args.engine


def printProgressBar (iteration, total, prefix = '', suffix = '', decimals = 1, length = 30, fill = '█', printEnd = "\r"):
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filledLength = int(length * iteration // total)
    bar = fill * filledLength + '-' * (length - filledLength)
    print(f'\r{prefix} |{bar}| {percent}% {suffix}', end = printEnd)
    # Print New Line on Complete
    if iteration == total: 
        print()

# accuracy logic by lichess (https://lichess.org/page/accuracy)
def get_accuracy_of_move(win_b, win_a):
    return 103.1668 * math.exp(-0.04354 * ((win_b) - (win_a))) - 3.1669


def get_accuracy_of_cp(a):
    return 103.1668 * math.exp(-0.04354 * a) - 3.1669


def calculate_wp(centipawns):
    return 50 + 50 * (2 / (1 + math.exp(-0.00368208 * centipawns)) - 1)


def analyze(pgn):
    game = chess.pgn.read_game(pgn)
    engine = chess.engine.SimpleEngine.popen_uci(ENGINE_PATH)
    game_annot = chess.pgn.Game()
    game_annot.headers = game.headers
    opening_book = chess.polyglot.open_reader(BOOK_PATH)

    analyzed_moves = []
    board = game.board()

    # analyze all the moves
    next_best_move = None
    in_book = True
    for move in game.mainline_moves():
        turn = board.turn

        book = False
        if in_book:
            for i in opening_book.find_all(board):
                if i.move == move:
                    book = True
                    break
            if not book:
                in_book = False

        forced = len(list(board.legal_moves)) == 1

        board.push(move)
        
        if board.is_checkmate():
            analyzed_moves.append(AnalyzedMove(
                score=0, 
                book=book,
                best=True,
                turn=turn,
                forced=forced,
                move=move
            ))
            break
        
        step = engine.play(board, chess.engine.Limit(depth=args.depth), info=chess.engine.Info.ALL)
        
        score = step.info["score"].white().score(mate_score=MATE_THRES)

        printProgressBar(len(analyzed_moves), len(list(game.mainline_moves())), suffix=f"{move} - {next_best_move}")

        best = next_best_move == move

        next_best_move = step.move
        
        analyzed_moves.append(AnalyzedMove(
            score=score, 
            book=book, 
            best=best, 
            turn=turn,
            forced=forced,
            move=move
        ))
    
    # now assign comments to all of the moves
    previous_score = 0
    winchance_loss = [0, 0]
    centpawn_n = [0, 0]
    accuracy = [[], []]
    main_node = game_annot.add_variation(analyzed_moves[0].move)
    final_sq = chess.square_name(analyzed_moves[0].move.to_square)
    main_node.comment =  f"[%c_effect {final_sq};square;{final_sq};type;Book;persistent;true]"
    index = 0
    
    for i in analyzed_moves[1:]:
        final_sq = chess.square_name(i.move.to_square)
        main_node = main_node.add_main_variation(i.move)

        if i.book:
            main_node.comment = f"[%c_effect {final_sq};square;{final_sq};type;Book;persistent;true]"
            continue
        elif i.forced:
            main_node.comment = f"[%c_effect {final_sq};square;{final_sq};type;Forced;persistent;true]"
            continue
        
        # get the accuracy of the move
        if i.best or round(previous_score, 2) == round(i.score, 2):
            i.best = True # update this if the move was equal to the best move
            acc = 100
        elif i.turn:
            acc = get_accuracy_of_move(calculate_wp(previous_score), calculate_wp(min(i.score, previous_score))) 
        else:
            acc = get_accuracy_of_move(calculate_wp(-previous_score), calculate_wp(-max(i.score, previous_score)))

        if i.best:
            centpawn_n[i.turn] += 1
        else:
            winchance_loss[i.turn] += calculate_wp(max((previous_score - i.score) if i.turn else -(previous_score - i.score), 0)) - 50
            
            centpawn_n[i.turn] += 1
        
        accuracy[i.turn].append(acc)

        had_improvement_opportunity = abs(analyzed_moves[index - 1].score - i.score) > 50

        if i.best:
            # check special case (aka great move)
            if index > 2: 
                if abs(analyzed_moves[index - 2].score - analyzed_moves[index - 1].score) > 150:
                    main_node.comment = f"[%c_effect {final_sq};square;{final_sq};type;GreatFind;persistent;true]"
                else:
                    main_node.comment = f"[%c_effect {final_sq};square;{final_sq};type;BestMove;persistent;true]"
            else:
                main_node.comment = f"[%c_effect {final_sq};square;{final_sq};type;BestMove;persistent;true]"
        elif acc > 95:
            main_node.comment = f"[%c_effect {final_sq};square;{final_sq};type;Excellent;persistent;true]"
        elif acc > 87:
            main_node.comment = f"[%c_effect {final_sq};square;{final_sq};type;Good;persistent;true]"
        elif acc > 70:
            main_node.comment = f"[%c_effect {final_sq};square;{final_sq};type;Inaccuracy;persistent;true]"
        elif acc > 20:
            if index > 3 and abs(analyzed_moves[index - 2].score - i.score) < 50 and had_improvement_opportunity:
                main_node.comment = f"[%c_effect {final_sq};square;{final_sq};type;Miss;persistent;true]"
            else:
                main_node.comment = f"[%c_effect {final_sq};square;{final_sq};type;Mistake;persistent;true]"
        else:
            if index > 3 and abs(analyzed_moves[index - 2].score - i.score) < 50 and had_improvement_opportunity:
                main_node.comment = f"[%c_effect {final_sq};square;{final_sq};type;Miss;persistent;true]"
            else:
                main_node.comment = f"[%c_effect {final_sq};square;{final_sq};type;Blunder;persistent;true]"

        previous_score = i.score
        index += 1
    
    # average centipawn loss
    winchance_loss[0] /= centpawn_n[0]
    winchance_loss[1] /= centpawn_n[1]
    
    # average accuracy values
    b_acc = 0
    for i in accuracy[0]: b_acc += i
    b_acc /= len(accuracy[0])

    w_acc = 0
    for i in accuracy[1]: w_acc += i
    w_acc /= len(accuracy[1])

    print(f"\nWhite Accuracy: {round(get_accuracy_of_cp((winchance_loss[1])), 1)}\nBlack Accuracy: {round(get_accuracy_of_cp((winchance_loss[0])), 1)}")
    print(f"White Winchance Loss: {round(winchance_loss[1])}\nBlack Winchance Loss: {round(winchance_loss[0])}")

    cleaned_name = args.pgn.replace(".pgn", "")
    print(game_annot, file=open(f"{cleaned_name}_analyzed.pgn", "w"), end="\n\n")
    engine.close()


if __name__ == "__main__":
    analyze(open(args.pgn))