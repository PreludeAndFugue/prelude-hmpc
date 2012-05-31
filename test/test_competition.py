

def test_competition_ranking():
    def scores(results):
        position = 1
        prev_score = 1000000
        new_results = []
        results.sort(reverse=True)
        for i, score in enumerate(results, start=1):
            if score < prev_score:
                position = i
                #position += 1
            new_results.append((position, score))
            prev_score = score
        return new_results

    print scores([1, 2, 3, 5, 6, 10, 8])
    print scores([5, 5, 5, 5])
    print scores([5, 4, 5, 3])
    print scores([1, 10, 2, 5, 5, 6, 10])

if __name__ == '__main__':
    test_competition_ranking()