from array import array
import os.path
import itertools
from collections import OrderedDict
from copy import deepcopy
import math
import random
import statistics
import multiprocessing
from functools import partial
import platform

from config import BIGRAMS_CONFIGS, LAYER_1_LETTERS, LAYER_2_LETTERS, LAYER_3_LETTERS, LAYER_4_LETTERS, VAR_LETTERS_L1_L2, MANUALLY_DEFINE_LAYERS, AUTO_LAYER_SWAP_COUNT, AUTO_LAYER_EMPTY_COUNT, AUTO_LAYER_IGNORE, FIXATE_MOST_COMMON_LETTER, FIXATED_LETTERS, NR_OF_LAYERS, NR_OF_BEST_LAYOUTS, PERFORM_GREEDY_OPTIMIZATION, SHOW_DATA, SHOW_GENERAL_STATS, SHOW_TOP_LAYOUTS, TEST_CUSTOM_LAYOUTS, CUSTOM_LAYOUTS, LETTERS_PER_LAYER, DISABLE_UNICODE, DEBUG_MODE, USE_MULTIPROCESSING, FILL_SYMBOL, SCORE_LIST, SCREEN_WIDTH
from helper_classes import BigramsConfig, ConfigSpecificResults
from ui_helpers import *

start_time = time()


def main():
    ###########################################################################################################################
    ###########################################################################################################################
    ################################################### Start of the script ###################################################
    ###########################################################################################################################
    ############################# (Edit `config.py` and `score_list.py` to influence the results) #############################
    ###########################################################################################################################
    ###########################################################################################################################

    # Make sure staticLetters and customLayouts are lowercase and properly formatted
    staticLetters = lowerStaticLetters(FIXATED_LETTERS)
    customLayouts = OrderedDict()
    for name, layout in CUSTOM_LAYOUTS:
        customLayouts[name] = xmlStrToOptStr(layout)

    # Validate the main error-hotspots in settings
    if validateSettings(staticLetters) is True:

        # Display configuration
        write('\n')
        displayTitle('Configurations')
        displaySubtitle('Bigrams')
        maxNameLen = max(len(config.name) for config in BIGRAMS_CONFIGS if config.weight)
        for config in BIGRAMS_CONFIGS:
            if config.weight:
                Info(
                    getPaddedText(config.name, maxNameLen + 1) +
                    getPaddedText(f'{config.weight}%', 4, left=True) +
                    f',    Path: {config.path}'
                )
                write('\n')
        write('\n')
    else:
        # If something is wrong, stop execution
        return

    # Calculate layer letters
    layerLetters = getLayerLetters()

    # Display layer letters
    if MANUALLY_DEFINE_LAYERS is False:
        if FIXATE_MOST_COMMON_LETTER:
            # Assigns a tuple to `staticLetters` where the first index is the most common letter.
            staticLetters = tuple(layerLetters[0][0] if i == 0 else "" for i in range(LETTERS_PER_LAYER))
        else:
            staticLetters = tuple("" * LETTERS_PER_LAYER)

        displaySubtitle('Layer letters (Generated)')
    else:
        displaySubtitle('Layer letters (Manual)')
    for i in range(4):
        Info(f'Layer {i + 1} letters:  {layerLetters[i]}')
        write('\n')
    half = len(layerLetters[4])//2
    Info(f'Variable letters: {layerLetters[4][:half]} {"<->" if DISABLE_UNICODE else "⇄"} {layerLetters[4][half:]}')
    if MANUALLY_DEFINE_LAYERS is False and FIXATE_MOST_COMMON_LETTER:
        Info(f'Fixated: \'{staticLetters[0]}\' on the bottom-right')
    write('\n\n')

    if DEBUG_MODE:
        write('\n')
    displayTitle('Optimization')
    displaySubtitle('Cycles for variable letters (Layers 1 and 2)')

    # Asciify the layer letters
    layer1letters = asciify(layerLetters[0])
    layer2letters = asciify(layerLetters[1])
    layer3letters = asciify(layerLetters[2])
    layer4letters = asciify(layerLetters[3])
    varLetters_L1_L2 = asciify(layerLetters[4])

    staticLetters = tuple(asciify(l) for l in staticLetters)

    # Get the letters for the layers possible with the letters you specified.
    firstLayers, secondLayers = getLayerCombinations(
        layer1letters, layer2letters, varLetters_L1_L2)
    #secondLayers, thirdLayers = getLayers(layer2letters, layer3letters, varLetters_L2_L3)
    nrOfCycles = len(firstLayers)

    # Prepare variables for later.
    tempLayoutList = []
    tempScoresList = []

    finalLayoutList = []
    finalScoresList = []

    if not DEBUG_MODE:
        # Create the cycles progress bar
        cyclesProgress = Progress(nrOfCycles)

    # Start the actual testing process
    for cycleNr, letters_L1 in enumerate(firstLayers):
        letters_L2 = secondLayers[cycleNr]
        ####################################################################################################################
        # Calculate the first Layer

        if DEBUG_MODE:
            print(f'\nCycle {cycleNr + 1} of {nrOfCycles}')
        else:
            cyclesProgress.set_status(f'Current cycle: {cycleNr + 1}')
            cyclesProgress.set_prog(cycleNr)

        # get the letters in layer 1 that can actually move.
        varLetters = getVariableLetters(letters_L1, staticLetters)

        # Get all layouts for each Layer with the current layer-letters.
        layouts_L1, layouts_L2, layouts_L3, layouts_L4 = getLayerPermutations(
            varLetters, staticLetters, letters_L2, layer3letters, layer4letters)

        # Test the layer 1 - layouts
        goodLayouts_L1, goodScores_L1 = testLayouts(layouts_L1)
        del layouts_L1

        # If the user says so, calculate the second layer.
        if NR_OF_LAYERS >= 2:
            ####################################################################################################################
            # Calculate the second Layer
            # Sort the best layer-1 layouts and only return the best ones
            bestLayouts_L1, bestScores_L1 = getTopScores(
                goodLayouts_L1, goodScores_L1)
            del goodLayouts_L1, goodScores_L1

            # Combine the layouts of layer 1 and layer 2 to all possible variants
            layouts_L1_L2 = combinePermutations(bestLayouts_L1, layouts_L2)
            del bestLayouts_L1, layouts_L2

            # Test the combined layouts of layer 1 and layer2
            goodLayouts_L1_L2, goodScores_L1_L2 = testLayouts(
                layouts_L1_L2, bestScores_L1)
            del layouts_L1_L2, bestScores_L1

            # Add the found layouts to the list (which will later be displayed)
            tempLayoutList.extend(goodLayouts_L1_L2)
            tempScoresList.extend(goodScores_L1_L2)
            del goodLayouts_L1_L2, goodScores_L1_L2
        else:
            # Add the found layouts to the list (which will later be displayed)
            tempLayoutList.extend(goodLayouts_L1)
            tempScoresList.extend(goodScores_L1)
            del goodLayouts_L1, goodScores_L1

    # Cycles completed
    if not DEBUG_MODE:
        cyclesProgress.set_status(f'Done')
        cyclesProgress.set_prog(nrOfCycles)

    if NR_OF_LAYERS >= 3:
        ####################################################################################################################
        # Calculate the third Layer

        if DEBUG_MODE:
            write('\n')
            displaySubtitle('Optimizing remaining layers')
            print('Layer 3')
            l3info = None
        else:
            write('\n\n')
            displaySubtitle('Optimizing remaining layers')
            l3info = InfoWithTime('Layer 3')

        nrOfBestPermutations = NR_OF_BEST_LAYOUTS * 2

        # Sort the best layer-1 layouts and only return the best ones
        bestLayouts_L1_L2, bestScores_L1_L2 = getTopScores(
            tuple(tempLayoutList), tempScoresList)
        del tempLayoutList, tempScoresList

        # Combine the layouts of layer 1 and layer 2 to all possible variants
        layouts_L1_L2_L3 = combinePermutations(bestLayouts_L1_L2, layouts_L3)
        bestLayouts_L1_L2, layouts_L3

        # Test the combined layouts of layers 1&2 and layer 3
        initialGoodLayouts_L1_L2_L3, initialGoodScores_L1_L2_L3 = testLayouts(
            layouts_L1_L2_L3, bestScores_L1_L2)
        del layouts_L1_L2_L3, bestScores_L1_L2

        if PERFORM_GREEDY_OPTIMIZATION:
            # Do an additional hillclimbing-optimization
            goodLayouts_L1_L2_L3, goodScores_L1_L2_L3 = greedyOptimization(
                initialGoodLayouts_L1_L2_L3, initialGoodScores_L1_L2_L3, l3info)
        else:
            goodLayouts_L1_L2_L3, goodScores_L1_L2_L3 = initialGoodLayouts_L1_L2_L3, initialGoodScores_L1_L2_L3
        del initialGoodLayouts_L1_L2_L3, initialGoodScores_L1_L2_L3

        if not DEBUG_MODE:
            l3info.set_done()
        write('\n')

        if NR_OF_LAYERS >= 4:
            ####################################################################################################################
            # Calculate the fourth Layer

            if DEBUG_MODE:
                print('Layer 4')
                l4info = None
            else:
                l4info = InfoWithTime('Layer 4')

            nrOfBestPermutations = nrOfBestPermutations * 5

            # Sort the best layer-1 layouts and only return the best ones
            bestLayouts_L1_L2_L3, bestScores_L1_L2_L3 = getTopScores(
                goodLayouts_L1_L2_L3, goodScores_L1_L2_L3)
            del goodLayouts_L1_L2_L3, goodScores_L1_L2_L3

            # Combine the layouts of layer 1 and layer 2 to all possible variants
            layouts_L1_L2_L3_L4 = combinePermutations(
                bestLayouts_L1_L2_L3, layouts_L4)
            del bestLayouts_L1_L2_L3, layouts_L4

            # Test the combined layouts of layers 1&2 and layer 3
            goodLayouts_L1_L2_L3_L4, goodScores_L1_L2_L3_L4 = testLayouts(
                layouts_L1_L2_L3_L4, bestScores_L1_L2_L3)
            del layouts_L1_L2_L3_L4, bestScores_L1_L2_L3

            if PERFORM_GREEDY_OPTIMIZATION:
                # Do an additional hillclimbing-optimization, then
                # add the found layouts to the list (which will later be displayed)
                finalLayoutList, finalScoresList = greedyOptimization(
                    goodLayouts_L1_L2_L3_L4, goodScores_L1_L2_L3_L4, l4info)
            else:
                finalLayoutList, finalScoresList = goodLayouts_L1_L2_L3_L4, goodScores_L1_L2_L3_L4
            del goodLayouts_L1_L2_L3_L4, goodScores_L1_L2_L3_L4

            if not DEBUG_MODE:
                l4info.set_done()
                write('\n')
            write('\n')

        else:
            # Do an additional hillclimbing-optimization, then
            # add the found layouts to the list (which will later be displayed)
            finalLayoutList, finalScoresList = goodLayouts_L1_L2_L3, goodScores_L1_L2_L3
            del goodLayouts_L1_L2_L3, goodScores_L1_L2_L3
    else:
        # Add the found layouts to the list (which will later be displayed). This happens if there is no layer 3 or 4.
        finalLayoutList = tempLayoutList
        finalScoresList = tempScoresList
        del tempLayoutList, tempScoresList

    displaySubtitle('Finished optimization')

    if SHOW_DATA is True:
        if TEST_CUSTOM_LAYOUTS is True:
            for name, layout in customLayouts.items():
                # If you're only testing a certain number of layers, only use that amount of layers in the name of the custom layouts.
                if len(layout) > (NR_OF_LAYERS*LETTERS_PER_LAYER):
                    customLayouts[name] = layout[:NR_OF_LAYERS *
                                                 LETTERS_PER_LAYER]

        # Display the data in the terminal.
        showDataInTerminal(finalLayoutList, finalScoresList, customLayouts)


def getLayerLetters() -> tuple:
    """Gets the letters to be used on each layer and returns them as a tuple of strings"""

    if MANUALLY_DEFINE_LAYERS is False:

        # Calculate layer letters
        monograms = generateMonogramsFromBigramFiles()
        letters = ''.join(sorted(monograms, key=lambda i: monograms[i], reverse=True))
        cutoff = LETTERS_PER_LAYER*4 - AUTO_LAYER_EMPTY_COUNT
        return \
         (letters[:min(LETTERS_PER_LAYER, cutoff)],
          letters[LETTERS_PER_LAYER:min(LETTERS_PER_LAYER*2, cutoff)],
          letters[LETTERS_PER_LAYER*2:min(LETTERS_PER_LAYER*3, cutoff)],
          letters[LETTERS_PER_LAYER*3:cutoff],
          letters[LETTERS_PER_LAYER - AUTO_LAYER_SWAP_COUNT:LETTERS_PER_LAYER + AUTO_LAYER_SWAP_COUNT])

    # Use manual layer letters
    return \
     (LAYER_1_LETTERS,
      LAYER_2_LETTERS,
      LAYER_3_LETTERS,
      LAYER_4_LETTERS,
      VAR_LETTERS_L1_L2)


def validateSettings(staticLetters) -> bool:
    """Checks the user's input for common errors. If everything is correct, returns `True`"""

    if MANUALLY_DEFINE_LAYERS is False:
        if not 0 <= AUTO_LAYER_SWAP_COUNT <= LETTERS_PER_LAYER:
            print(f'AUTO_LAYER_SWAP_COUNT must be between 0 and {LETTERS_PER_LAYER} (inclusive)')
            return False
        if not 0 <= AUTO_LAYER_EMPTY_COUNT <= LETTERS_PER_LAYER*3:
            print(f'AUTO_LAYER_EMPTY_COUNT must be between 0 and {LETTERS_PER_LAYER*3} (inclusive)')
            return False
        if AUTO_LAYER_SWAP_COUNT + AUTO_LAYER_EMPTY_COUNT > LETTERS_PER_LAYER*3:
            print(f'AUTO_LAYER_SWAP_COUNT cannot be greater than {LETTERS_PER_LAYER*3 - AUTO_LAYER_EMPTY_COUNT} with AUTO_LAYER_EMPTY_COUNT = {AUTO_LAYER_EMPTY_COUNT}')
            return False
    else:
        layout = LAYER_1_LETTERS + LAYER_2_LETTERS + LAYER_3_LETTERS + LAYER_4_LETTERS
        # Check for duplicate letters
        for char in layout:
            if (char != FILL_SYMBOL) and (layout.count(char) > 1):
                print("Duplicate letters found:", char,
                      "\nCheck LAYER_1_LETTERS, LAYER_2_LETTERS, LAYER_3_LETTERS, and LAYER_4_LETTERS")
                return False
        # Check whether VAR_LETTERS_L1_L2's letters are contained in the layers 1 & 2
        for char in VAR_LETTERS_L1_L2:
            if char not in LAYER_1_LETTERS + LAYER_2_LETTERS:
                print(
                    '"', char, '" was defined in VAR_LETTERS_L1_L2, but is not part of layer 1 or 2')
                return False
        # Check whether fixed_letters's letters are contained in the first layers
        for char in staticLetters:
            if char not in LAYER_1_LETTERS:
                print(
                    '"', char, '" was defined in staticLetters, but is not part of the first layer')
                return False
    # Check if bigram-settings are valid
    if len(BIGRAMS_CONFIGS) == 0:
        print("No bigrams-config found.")
        return False
    else:
        weightSum = 0
        for config in BIGRAMS_CONFIGS:
            if os.path.exists(config.path) is False:
                print("The bigram-path you provided does not point to an existing file.")
                print("Language:", config.name, "\nPath:", config.path)
                return False
            weightSum += config.weight
        if weightSum != 100:
            print("The weights of BIGRAMS_CONFIGS did not add up to 100 (%).")
            return False
    return True


def normalizeDict(dictionary: dict) -> dict:
    """Returns a normalized version of a dictionary of frequencies"""
    total = sum(dictionary.values())
    return {key: dictionary[key]/total for key in dictionary}


def generateMonogramsFromBigramFiles(configs: tuple = BIGRAMS_CONFIGS) -> dict:
    """Uses the bigram-files to generate and return a monogram dictionary"""

    # Generate monogram dicts for each language
    # Store them with their weights
    normalizedMonogramLists = []
    for config in configs:
        if config.weight <= 0:
            continue
        with open(config.path, 'r', encoding='utf-8') as corpus:
            bigrams = {line[:2].lower(): float(line[3:]) for line in corpus}
        monograms = dict()
        for bigram in bigrams:
            for char in bigram:
                if char in AUTO_LAYER_IGNORE:
                    continue
                if char in monograms:
                    monograms[char] += bigrams[bigram]
                else:
                    monograms[char] = bigrams[bigram]
        normalizedMonogramLists.append((normalizeDict(monograms), config.weight))

    # Combine the monogram dicts into one dict by using their weights
    combinedMonograms = dict()
    for monograms, weight in normalizedMonogramLists:
        for char in monograms:
            if char in combinedMonograms:
                combinedMonograms[char] += monograms[char]*weight
            else:
                combinedMonograms[char] = monograms[char]*weight

    # Not needed for now, but will make the frequencies sum to 1.0
    #combinedMonograms = normalizeDict(combinedMonograms)

    return combinedMonograms


# Used in combination with the `asciify` and `deAsciify` functions
replacedWithAscii = dict()
monograms = generateMonogramsFromBigramFiles()
mostFreqLetters = sorted(monograms, key=lambda i: monograms[i], reverse=True)[:256-LETTERS_PER_LAYER*NR_OF_LAYERS]
asciiReplacementChars = [chr(i) for i in range(256) if chr(i) not in mostFreqLetters and chr(i) != FILL_SYMBOL]


def asciify(string: str) -> str:
    """Take a string and replace all non-ascii-chars with ascii-versions of them"""
    result = list(string)
    for idx, char in enumerate(string):
        try:
            char.encode('ascii')
        except UnicodeEncodeError:
            if char in replacedWithAscii:
                result[idx] = replacedWithAscii[char]
            else:
                replacedWithAscii[char] = asciiReplacementChars[-1]
                asciiReplacementChars.pop()
                result[idx] = replacedWithAscii[char]
    return ''.join(result)


def deAsciify(string: str) -> str:
    """Take turn all replacement-ascii-chars and turn them back into their original forms."""
    result = list(string)
    for idx, char in enumerate(string):
        for replacedChar, asciiChar in replacedWithAscii.items():
            if char == asciiChar:
                result[idx] = replacedChar
    return ''.join(result)


def getLayerCombinations(layer1letters: str, layer2letters: str, varLetters_L1_L2: str) -> tuple:
    """Creates all possible layer-combinations with the letters you specified.
    This includes "varLetters_L1_L2" and "varLetters_L2_L3"
    It always returns two List (of strings)."""

    if varLetters_L1_L2:  # Only do all this stuff if there actually exist variable letters.

        L1_Layers = []
        L2_Layers = []

        nrFlexLetters_L1 = round(len(varLetters_L1_L2)/2)
        nrFlexLetters_L2 = len(varLetters_L1_L2) - nrFlexLetters_L1

        fixLetters_L1 = layer1letters[:-nrFlexLetters_L1]
        fixLetters_L2 = layer2letters[nrFlexLetters_L2:]

        j = 0
        # Go through every combination of (variable) letters
        for combination in itertools.permutations(varLetters_L1_L2):
            addCombination = True

            combination = ''.join(combination)
            varLetters_L1 = sorted(combination[:nrFlexLetters_L1])
            varLetters_L1 = ''.join(varLetters_L1)

            # See if there already exists a versions of the same layer
            for prevCombination in L1_Layers:
                if varLetters_L1 == prevCombination[-nrFlexLetters_L1:]:
                    addCombination = False
                    break

            # Only add letter-combinations that are new
            if addCombination is True:
                L1_LayerLetters = fixLetters_L1 + varLetters_L1
                L2_LayerLetters = combination[nrFlexLetters_L1:] + \
                    fixLetters_L2

                L1_Layers.append(L1_LayerLetters)
                L2_Layers.append(L2_LayerLetters)

                if DEBUG_MODE is True:
                    print(f'DEBUG: {L1_Layers[j]} {L2_Layers[j]}')

                j += 1
        return L1_Layers, L2_Layers

    else:  # if there are no variable letters between layer 1 and 2, do nothing.
        return [layer1letters], [layer2letters]


def getVariableLetters(fullLayer: str, staticLetters: tuple) -> str:
    """Extracts the non-fix letters for the first layer."""
    varLetters = ''

    if staticLetters:
        for i in range(len(fullLayer)):
            if not fullLayer[i] in staticLetters:
                varLetters += fullLayer[i]
    else:
        varLetters = fullLayer

    return varLetters


bigramCache = dict()


def getBigrams(sortedLetters: str, configs: tuple = BIGRAMS_CONFIGS) -> tuple:
    """This opens the bigram-list (the txt-file) and returns the letters and the frequencies of the required bigrams."""
    if configs == BIGRAMS_CONFIGS and sortedLetters in bigramCache:
        return bigramCache[sortedLetters]
    else:
        # Prepare the bigram-letters
        fullBigramList = []
        for bigram in itertools.permutations(sortedLetters, 2):
            fullBigramList.append(''.join(bigram))
        # Add duplicate letter bigrams. ("aa", "ee", "nn", "rr", ...)
        for letter in sortedLetters:
            fullBigramList.append(letter+letter)

        # Filter out the bigrams that contain the predefined filler-symbol.
        bigramList = [b for b in fullBigramList if FILL_SYMBOL not in b]
        # Make sure we also will get the replaced letters from the dictionary.
        for i, bigram in enumerate(bigramList):
            bigramList[i] = deAsciify(bigram)
        # Create a set for faster lookups
        bigramsSet = set(bigramList)

        normalizedCorpora = []
        for config in configs:
            if config.weight <= 0:
                continue

            # Sum up the corpus's frequencies. Used for later normalization.
            frequencySum = 0
            with open(config.path, 'r', encoding='utf-8') as corpus:
                for line in corpus:
                    frequency = float(line[line.find(' ')+1:])
                    frequencySum += frequency

            # Read the file and normalize its contents.
            normalizedCorpus = []
            with open(config.path, 'r', encoding='utf-8') as corpus:
                for line in corpus:
                    bigram = line[:2].lower()
                    if bigram in bigramsSet:
                        frequency = float(line[line.find(' ')+1:])
                        normalizedFrequency = frequency * config.weight / frequencySum
                        normalizedCorpus.append((
                            bigram,
                            normalizedFrequency,
                        ))
            normalizedCorpora.append(normalizedCorpus)

        bigramsDict = dict()
        for corpus in normalizedCorpora:
            for bigram, freq in corpus:
                if bigram not in bigramsDict:
                    bigramsDict[bigram] = freq
                else:
                    bigramsDict[bigram] += freq

        bigrams = tuple(Bigram(characters, freq)
                        for characters, freq in bigramsDict.items())
        if configs == BIGRAMS_CONFIGS:
            bigramCache[sortedLetters] = bigrams
        return bigrams


def filterBigrams(bigrams: tuple, requiredLetters=[]) -> tuple:
    """Trims the bigram-list to make getPermutations() MUCH faster.
    It basically removes all the bigrams that were already tested."""  # I'm amazing.

    indicesToKeep = []
    for j, bigram in enumerate(bigrams):
        bigramLetters = bigram.getAsciifiedLetters()

        keepBigram = True
        for letterGroup in requiredLetters:
            foundALetter = False
            for letter in letterGroup:
                if letter in bigramLetters:
                    foundALetter = True
            if foundALetter is False:
                keepBigram = False
                break

        if keepBigram is True:  # Remove the redundant bigrams
            indicesToKeep.append(j)

    trimmedBigrams = tuple(bigrams[index] for index in indicesToKeep)
    return trimmedBigrams


def lowerStaticLetters(staticLetters: tuple) -> tuple:
    """Takes any tuple and turns its uppercase letters into lowercase ones."""
    lst = list(staticLetters)
    for j, element in enumerate(staticLetters):
        lst[j] = element.lower()
    return tuple(lst)


def getLayerPermutations(varLetters: str, staticLetters: tuple, layer2letters: str, layer3letters: str, layer4letters: str) -> tuple:
    """Creates and returns a list of layouts."""

    layer1layouts = getPermutations(varLetters, staticLetters)
    layer2layouts = ['']
    layer3layouts = ['']
    layer4layouts = ['']

    if NR_OF_LAYERS >= 2:
        if len(layer2letters) == LETTERS_PER_LAYER:
            layer2layouts = getPermutations(layer2letters)
        elif len(layer2letters) < LETTERS_PER_LAYER:
            layer2layouts = fillAndPermuteLayout(layer2letters)
        else:
            print("Error: too many letters in second layer")
    if NR_OF_LAYERS >= 3:
        if len(layer3letters) == LETTERS_PER_LAYER:
            layer3layouts = getPermutations(layer3letters)
        elif len(layer3letters) < LETTERS_PER_LAYER:
            layer3layouts = fillAndPermuteLayout(layer3letters)
        else:
            print("Error: too many letters in third layer")
    if NR_OF_LAYERS == 4:
        if len(layer4letters) == LETTERS_PER_LAYER:
            layer4layouts = getPermutations(layer4letters)
        elif len(layer4letters) < LETTERS_PER_LAYER:
            layer4layouts = fillAndPermuteLayout(layer4letters)
        else:
            print("Error: too many letters in fourth layer")

    return layer1layouts, layer2layouts, layer3layouts, layer4layouts


def getPermutations(varLetters: str, staticLetters=[]) -> tuple:
    """Returns all possible letter-positions (permutations) with the input letters."""

    layouts = ['']*math.factorial(len(varLetters))

    if len(staticLetters) > 0:  # this only activates for layer 1 (which has static letters)
        # try every layout
        for layoutIteration, letterCombination in enumerate(itertools.permutations(varLetters)):
            j = 0
            for letterPlacement in range(LETTERS_PER_LAYER):
                if staticLetters[letterPlacement] != '':
                    layouts[layoutIteration] += staticLetters[letterPlacement]
                else:
                    layouts[layoutIteration] += letterCombination[j]
                    j += 1

    else:  # This is used for all layers except for layer 1
        # try every layout
        for layoutIteration, letterCombination in enumerate(itertools.permutations(varLetters)):
            layouts[layoutIteration] = ''.join(letterCombination)

    return tuple(layouts)


def fillAndPermuteLayout(letters: str) -> tuple:
    """Creates full layouts out of only a few letters, while avoiding redundancy.
    It is primarily important for layer 4, which many alphabets do not completely fill with letters."""
    missingSlotCount = LETTERS_PER_LAYER - len(letters)
    newLetters = letters + (FILL_SYMBOL * missingSlotCount)

    permutations = itertools.permutations(newLetters)  # Get permutations
    layouts = set(''.join(letterList)
                  for letterList in permutations)  # Remove all duplicates

    return tuple(layouts)


def testLayouts(layouts: tuple, prevScores=None) -> tuple:
    """Calculates the best layouts and returns them (and their scores)."""

    # Combine the Letters for the layer 1 and layer 2
    layoutLetters = layouts[0]
    # Get the letters of the last layer calculated. (if you're only calculating one layer, this is what you get.)
    lastLayerLetters = layoutLetters[-LETTERS_PER_LAYER:]

    if DEBUG_MODE is True:
        print(f'DEBUG: {lastLayerLetters}')

    # Get the bigrams for the input letters
    bigrams = getBigrams(''.join(sorted(layoutLetters)))

    # Filter out the previous bigrams if there are any that need filtering.
    if len(layoutLetters) > LETTERS_PER_LAYER:
        bigrams = filterBigrams(bigrams, [lastLayerLetters])

    if USE_MULTIPROCESSING is True:
        if prevScores:
            if len(prevScores) > 1:
                goodLayouts = []
                goodScores = array("d", [])
                # Prepare the group-sizes of the layout-groups for multiprocessing
                groupBeginnings = []
                for j in range(len(prevScores)):
                    # Prepare the iterables for the later "pool.map"
                    groupBeginnings.append(
                        int((len(layouts) / len(prevScores)) * j))
                groupSize = groupBeginnings[1]

                # Prepare the layout-testing-function and its "static parameters"
                testingFunction = partial(getLayoutScores_multiprocessing, [
                                          layouts, bigrams, prevScores, groupSize])

                # Using multithreading, test the layouts for their flow. Only test <= 20 at once.
                maxNrProcesses = 15  # Max number of simultaneous processes
                j = 0
                while j < len(prevScores):
                    resultsList = []

                    # Using multithreading, test the layouts for their flow
                    with multiprocessing.Pool(processes=len(prevScores[j:j+maxNrProcesses])) as pool:
                        resultsList = pool.map(
                            testingFunction, groupBeginnings[j:j+maxNrProcesses])

                    # Add the results to the goodLayouts- and goodScores-lists
                    for results in resultsList:
                        goodLayouts.extend(results[0])
                        goodScores.extend(results[1])
                    j += maxNrProcesses
                goodLayouts = tuple(goodLayouts)

            else:
                # Test the layouts for their flow
                goodLayouts, goodScores = getLayoutScores(
                    layouts, bigrams, prevScores)
        else:
            # Test the layouts for their flow
            goodLayouts, goodScores = getLayoutScores(
                layouts, bigrams, prevScores)
    else:
        # Test the layouts for their flow
        goodLayouts, goodScores = getLayoutScores(
            layouts, bigrams, prevScores)

    return goodLayouts, goodScores


def testSingleLayout(layout: str, asciiArray: array, bigrams: tuple) -> float:
    """A toned-down version of testLayouts() and is only tests one layout per call."""

    # Get the bigrams that contain [orderedLetters]
    for j, letter in enumerate(layout):
        asciiArray[ord(letter)] = j  # Fill up asciiArray

    score = 0.0
    for bigram in bigrams: # Go through every bigram and see how well it flows.
        firstLetterPlacement = asciiArray[bigram.letter1AsciiCode]
        secondLetterPlacement = asciiArray[bigram.letter2AsciiCode]
        score += bigram.frequency * SCORE_LIST[firstLetterPlacement][secondLetterPlacement]

    return score


def getAsciiArray() -> array:
    """An array that for the ord()-number of a letter can hold that letter's position-number on the keyboard.
    Used when testing layouts.
    This function is a shortcut to make sure all `asciiArray`s are exactly the same, without using a global variable."""
    return array("B", [0]*256)


def getLayoutScores(layouts: tuple, bigrams: tuple, prevScores=None) -> tuple:
    """Tests the layouts and return their scores. It's only used when single-threading."""

    asciiArray = getAsciiArray()
    nrLayouts = len(layouts)
    scores = array("d", [0.0]*nrLayouts) # Create the empty scoring-list

    # Test the flow of all the layouts.
    for k, layout in enumerate(layouts):
        for j, letter in enumerate(layout):
            asciiArray[ord(letter)] = j  # Fill up asciiArray

        for bigram in bigrams: # Go through every bigram and see how well it flows.
            firstLetterPlacement = asciiArray[bigram.letter1AsciiCode]
            secondLetterPlacement = asciiArray[bigram.letter2AsciiCode]
            scores[k] += bigram.frequency * SCORE_LIST[firstLetterPlacement][secondLetterPlacement]

    if prevScores:
        # Add the previous layouts' scores. (which weren't tested here. It would be redundant.)
        for j in range(len(prevScores)):
            groupSize = int((nrLayouts / len(prevScores)))
            groupBeginning = groupSize * j
            groupEnding = groupSize * (j+1)

            for k in range(groupBeginning, groupEnding):
                scores[k] += prevScores[j]

    goodLayouts, goodScores = getTopScores(layouts, scores, 500)
    return goodLayouts, goodScores


def getLayoutScores_multiprocessing(*args) -> tuple:
    """This function tests the layouts and return their scores.
    Only use this function when using multiprocessing. Otherwise, use [getLayoutScores]"""

    # Rename the input arguments
    staticArgs = args[0]
    mapArgs = args[1]

    groupSize = staticArgs[3]

    groupBeginning = mapArgs
    groupEnding = groupBeginning + groupSize
    allLayouts = staticArgs[0]

    layouts = allLayouts[groupBeginning: groupEnding]
    bigrams = staticArgs[1]

    asciiArray = getAsciiArray()
    prevScore = staticArgs[2][int(groupBeginning/groupSize)]
    scores = array("d", [prevScore]*groupSize)

    # Test the flow of all the layouts.
    for k, layout in enumerate(layouts):
        for j, letter in enumerate(layout):
            asciiArray[ord(letter)] = j  # Fill up asciiArray

        for bigram in bigrams: # Go through every bigram and see how well it flows.
            firstLetterPlacement = asciiArray[bigram.letter1AsciiCode]
            secondLetterPlacement = asciiArray[bigram.letter2AsciiCode]
            scores[k] += bigram.frequency * SCORE_LIST[firstLetterPlacement][secondLetterPlacement]

    # Only use the best scores (and layouts) for performance-reasons
    goodLayouts, goodScores = getTopScores(layouts, scores, 500)
    return goodLayouts, goodScores


def getTopScores(layouts: tuple, scores: array, nrOfBest=NR_OF_BEST_LAYOUTS) -> tuple:
    """Returns the best [whatever you set "nrOfBestPermutations" to] layouts with their scores.
    The LAST items of those lists should be the best ones."""

    # Make sure we don't try to get more scores than actually exist
    if nrOfBest > len(scores):
        nrOfBest = len(scores)

    lenScores = len(scores)
    indices = range(lenScores)

    # BEFORE sorting the lists, make sure they're not unnecessarily large
    while lenScores > nrOfBest*3 and lenScores > LETTERS_PER_LAYER*2:
        mean = statistics.mean(scores[idx] for idx in indices)
        # Get all indices & scores that are above the mean of the remaining scores.
        # This more than halves remaining scores.
        indices = [i for i, score in enumerate(scores) if score >= mean]

        newLength = len(indices)
        if newLength == lenScores:
            # If scores aren't filtered anymore, stop the loop
            break
        else:
            lenScores = newLength
    else:
        # Do this after the loop has finished.
        # Get the remaining (best) scores using the filtered indices.
        scores = [scores[idx] for idx in indices]

    # Sort scores & indices. This is way faster thanks to the above while-loop
    sortedScoreIdxTuples = sorted(zip(scores, indices))

    topScores, topIndices = zip(*sortedScoreIdxTuples[-nrOfBest:])
    topLayouts = tuple(layouts[idx] for idx in topIndices)
    topScores = array("d", topScores)

    return topLayouts, topScores


def combinePermutations(list1: tuple, list2: tuple) -> tuple:
    """Creates all possible permutations of two tuples while still keeping them in the right order. (first, second) (a, then b)"""
    listOfStrings = []

    for a in list1:
        listOfStrings.extend(a + b for b in list2)

    return tuple(listOfStrings)


def greedyOptimization(layouts: tuple, scores: array, info: InfoWithTime = None) -> tuple:
    """Randomly switches letters in each of the layouts to see whether the layouts can be improved this way."""

    optimizedLayouts = dict(zip(layouts, scores))
    asciiArray = getAsciiArray()
    bigrams = getBigrams(''.join(sorted(layouts[0])))
    if DEBUG_MODE:
        print(f'DEBUG: Greedy optimization with {len(layouts)} layouts')
    else:
        info.set_status(f'{len(layouts)} layouts] [Greedy optimization')
    for layout, score in zip(layouts, deepcopy(scores)):
        optimizing = True
        while optimizing is True:
            layoutPermutations = performLetterSwaps(layout)
            for i, permutatedLayout in enumerate(layoutPermutations):
                permutatedScore = testSingleLayout(
                    permutatedLayout, asciiArray, bigrams)
                if permutatedScore > score:
                    layout = permutatedLayout
                    score = permutatedScore
                    break
                elif i+1 == len(layoutPermutations):
                    optimizing = False
        if layout not in optimizedLayouts:
            optimizedLayouts[layout] = score
    if DEBUG_MODE:
        print(f'DEBUG: Finished with {len(optimizedLayouts)} layouts')

    return tuple(optimizedLayouts.keys()), array("d", optimizedLayouts.values())


def performLetterSwaps(layout: str) -> set:
    """Get all layouts that are possible through 2-letter-swaps."""
    layouts = set([layout])
    originalLayout = tuple(layout)
    for idx1 in range(len(layout)):
        for idx2 in range(idx1+1, len(layout)):
            copy = list(originalLayout)
            copy[idx1], copy[idx2] = copy[idx2], copy[idx1]
            layoutStr = ''.join(copy)
            if layoutStr not in layouts:
                layouts.add(layoutStr)
    return layouts


def showDataInTerminal(
    layouts: tuple,
    scores: array,
    customLayouts=OrderedDict(),
) -> None:
    """Displays the results; The best layouts, maybe (if i decide to keep this in here) the worst, and some general data."""

    if SHOW_TOP_LAYOUTS > 0:
        if SHOW_TOP_LAYOUTS == 1:
            displayTitle('The King')
        else:
            displayTitle(f'The {SHOW_TOP_LAYOUTS} best layouts')

        layouts, _ = getTopScores(layouts, scores, SHOW_TOP_LAYOUTS)
        del scores
        for idx, layout in enumerate(reversed(layouts)):
            printLayoutData(layout, placing=idx+1)
        displaySeparator()

    if TEST_CUSTOM_LAYOUTS is True:
        write('\n')
        displayTitle(f'Custom layouts')

        for name, layout in customLayouts.items():
            printLayoutData(layout, name=name)

    if SHOW_GENERAL_STATS is True:
        # Get all bigrams that actually can be written using this layout.
        writeableBigrams = getBigrams(''.join(sorted(layouts[0])))
        # Get the sum of those ^ frequencies.
        writeableFrequencySum = sum(
            bigram.frequency for bigram in writeableBigrams)

        if SHOW_TOP_LAYOUTS == 0:
            print('\n')
        write('\n')
        displayTitle('General stats')
        Info(f'Total execution time: {getFormattedTime(time() - start_time)}')
        write('\n')
        Info(f'Amount of bigrams that can be written with the letters used in this layout: {writeableFrequencySum:.2f}%')
        write('\n\n')


def optStrToXmlStr(layout: str) -> str:
    """Turns the string-representation which is used internally into one that aligns with 8vim's XML-formatting."""

    b = "{6}{7}{14}{15}{22}{23}{30}{31} {0}{1}{8}{9}{16}{17}{24}{25} {2}{3}{10}{11}{18}{19}{26}{27} {4}{5}{12}{13}{20}{21}{28}{29}"
    layout = deAsciify(layout)
    return b.format(*layout) + "\n" + b.format(*layout.upper())


def xmlStrToOptStr(layout: str) -> str:
    """Turns a layout which uses 8vim's XML-formatting into the string-representation which is used internally while optimizing."""

    b = "{8}{9}{16}{17}{24}{25}{0}{1} {10}{11}{18}{19}{26}{27}{2}{3} {12}{13}{20}{21}{28}{29}{4}{5} {14}{15}{22}{23}{30}{31}{6}{7}"
    layout = layout.replace(' ', '')  # Remove whitespaces
    layout = asciify(layout)
    layout = b.format(*layout)
    layout = layout.replace(' ', '')  # Remove whitespaces
    return layout


def layoutVisualisation(layout: str) -> str:
    """Takes the layout-letters and gives a visual representation of them.
    Currently only supports layouts with 4-sections."""
    blueprint = """   \\  {27}         {28}  /
 {26}  \\  {19}       {20}  /  {29}
  {18}  \\  {11}     {12}  /  {21}
   {10}  \\  {3}   {4}  /  {13}
    {2}  \\ _____ /  {5}
        |     |
        |_____|
    {1}  /       \\  {6}
   {9}  /  {0}   {7}  \\  {14}
  {17}  /  {8}     {15}  \\  {22}
 {25}  /  {16}       {23}  \\  {30}
   /  {24}         {31}  \\ """ if DISABLE_UNICODE else """ ⟍  {27}                {28} ⟋
 {26} ⟍  {19}            {20} ⟋  {29}
   {18} ⟍  {11}        {12} ⟋  {21}
     {10} ⟍  {3}    {4} ⟋  {13}
       {2} ⟍     ⟋  {5}
           ⟍ ⟋
           ⟋ ⟍
       {1} ⟋     ⟍  {6}
     {9} ⟋  {0}    {7} ⟍  {14}
   {17} ⟋  {8}        {15} ⟍  {22}
 {25} ⟋  {16}            {23} ⟍  {30}
 ⟋  {24}                {31} ⟍"""
    layout = deAsciify(layout)
    while len(layout) < 32:
        layout += " "
    layout = layout.replace(FILL_SYMBOL, '-' if DISABLE_UNICODE else '░')
    return blueprint.format(*layout)


def getConfigSpecificData(layout: str) -> list:
    """Get all necessary `ConfigSpecificResults`s, according to the provided layout & config."""

    layout = ''.join(letter for letter in layout if letter != FILL_SYMBOL)
    configSpecificData = [ConfigSpecificResults(
        "All",
        100,
        getBigrams(layout),
    )]
    for config in BIGRAMS_CONFIGS:
        originalWeight = config.weight
        fullWeightConfig = config.fullWeightClone()

        configSpecificData.append(ConfigSpecificResults(
            config.name,
            originalWeight,
            getBigrams(layout, (fullWeightConfig, )),
        ))
    return configSpecificData


def printLayoutData(layout: str, placing: int = None, name: str = None) -> None:
    """A function that positions and prints information
    next to the layout-display-string for more compact visuals."""

    displaySeparator()
    visLayout = layoutVisualisation(layout)
    visLayoutLines = visLayout.split('\n')

    lineToPrint = 0
    if placing is not None:
        print(getExpandedLine(left=visLayoutLines[lineToPrint], right=f'Layout-placing: {placing}'))
        lineToPrint += 1
    if name is not None:
        print(getExpandedLine(left=visLayoutLines[lineToPrint], right=name))
        lineToPrint += 1

    print(visLayoutLines[lineToPrint])
    lineToPrint += 1

    xmlStr = optStrToXmlStr(layout)
    xmlStrParts = xmlStr.split('\n')
    for xmlStrPart in xmlStrParts:
        print(getExpandedLine(left=visLayoutLines[lineToPrint], right=xmlStrPart))
        lineToPrint += 1

    print(visLayoutLines[lineToPrint])
    lineToPrint += 1

    configSpecificData = getConfigSpecificData(layout)
    maxVisNameLen = max(len(i.name) for i in configSpecificData if i.name != 'All')
    asciiArray = getAsciiArray()
    for data in configSpecificData:
        try:
            visLine = visLayoutLines[lineToPrint]
        except IndexError:
            visLine = ""

        lineToPrint += 1
        cfgName = data.name
        weight = data.weight
        score = testSingleLayout(layout, asciiArray, data.bigrams)
        if cfgName == "All":
            visName = "All Languages "
            offset = 0
        else:
            #visName = cfgName + " {}% ".format(weight)
            visName = getPaddedText(cfgName, maxVisNameLen + 1) + getPaddedText(f'{weight}% ', 5, left=True)
            offset = 14
        infoStr = " "*offset + visName
        infoStr += ('-' if DISABLE_UNICODE else '─')*(LETTERS_PER_LAYER*NR_OF_LAYERS +
                        NR_OF_LAYERS-len(visName)-offset)
        infoStr += f'> Score: {score:.4f}'
        print(getExpandedLine(left=visLine, right=infoStr))

    if lineToPrint < len(visLayoutLines):
        for visLine in visLayoutLines[lineToPrint:]:
            print(visLine)


class Bigram:
    def __init__(self, bigramCharacters: str, frequency: float):
        # Make sure the bigrams we're actually using only consist of ascii-characters.
        bigramCharacters = asciify(bigramCharacters)
        # Turn the characters into integers, representing their ascii-code.
        self.letter1AsciiCode = ord(bigramCharacters[0])
        self.letter2AsciiCode = ord(bigramCharacters[1])
        self.frequency = frequency

    def getAsciifiedLetters(self) -> str:
        return chr(self.letter1AsciiCode) + chr(self.letter2AsciiCode)

    def getRealLetters(self) -> str:
        return deAsciify(self.getAsciifiedLetters())


if __name__ == '__main__':
    Cursor.hide()
    try:
        main()
    finally:
        Cursor.show()
