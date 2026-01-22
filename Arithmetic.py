import sys
import os
import collections

MAX_VAL = 65535 #макс 2^16 - 1      
HALF_VAL = 32768  #половина
Q1_VAL = 16384 #1 чет
Q3_VAL = 49152 #3 чет

#считает сколько раз встречается каждый символ
def analyze_symbols(data):
    counter = collections.Counter(data)#счетчик
  
    symbols = sorted([bytes([b]) for b in counter.keys()])# список символов
    
    freqs = [counter[s[0]] for s in symbols]# список частот
    
    c_summa = [0]# кум сумма
    total = 0# крлво
    for f in freqs:
        total += f
        c_summa.append(total)
    
    return symbols, freqs, c_summa, total

#сжимает данные через арифметическое кодирование
def arithmetic_encode(data):
    symbols, freqs, c_summa, total = analyze_symbols(data)

    low = 0# нмз
    high = MAX_VAL# верх
    wait = 0# отложенные биты
   
    bit_buffer = 0# текущее значение
    bit_count = 0# колво
    output = bytearray()# результат

    # записывает накопленные биты в байты
    def bits_to_byte():
        nonlocal bit_buffer, bit_count, output
        
        while bit_count >= 8:
            byte = (bit_buffer >> (bit_count - 8)) & 0xFF# извлекаем старшие 8
            output.append(byte)
            bit_count -= 8
            bit_buffer &= (1 << bit_count) - 1# очищаем
    
    # добавляет биты в буфер
    def add_bits(bits_to_add, count):
        nonlocal bit_buffer, bit_count
        
        bit_buffer = (bit_buffer << count) | bits_to_add# сдвиг и добавление
        bit_count += count
    
        bits_to_byte()#записываем
    
    for byte in data:# кодирование 
        sym = bytes([byte])
        idx = symbols.index(sym)
       
        sym_low = c_summa[idx]# нижняя кум сумма
        sym_high = c_summa[idx + 1]# верхняя
    
        range_size = high - low + 1
        high = low + (range_size * sym_high) // total - 1# новый низ
        low = low + (range_size * sym_low) // total# новый верх
        
        while True:# маштабирование
            if high < HALF_VAL:# 1) когда весь интервал в нижней половине
                add_bits(0, 1) 
                for i in range(wait):
                    add_bits(1, 1)
                wait = 0
          
            elif low >= HALF_VAL:#2) когда в верхней
                add_bits(1, 1)  
                for i in range(wait):
                    add_bits(0, 1)
                wait = 0
                low -= HALF_VAL
                high -= HALF_VAL
            
            elif low >= Q1_VAL and high < Q3_VAL:#3) в средней четверти
                wait += 1
                low -= Q1_VAL
                high -= Q1_VAL
            
            else:
                break # 4) не нужно

            low <<= 1# удваиваем и добавляем 1 в младший
            high = (high << 1) | 1

    wait += 1
    # выводим последнии биты
    if low < Q1_VAL:
        add_bits(0, 1)  
        for i in range(wait):
            add_bits(1, 1) 
    else:
        add_bits(1, 1) 
        for i in range(wait):
            add_bits(0, 1) 
    
    if bit_count > 0:# если есть неполные то добиваем 0
        bit_buffer <<= (8 - bit_count)
        output.append(bit_buffer)
    
    return symbols, freqs, bytes(output)

#восстанавливает оригинальные данные
def arithmetic_decode(symbols, freqs, encoded_data, original_length):
    c_summa = [0]
    total = 0
    for f in freqs:
        total += f
        c_summa.append(total)
    
    bit_pos = 0# позиция бита в байте
    current_byte = 0#текущий байт
    byte_index = 0# индекс байта
    
    def read_bit():# читает бит
        nonlocal bit_pos, current_byte, byte_index
        
        if byte_index >= len(encoded_data):# если до конца дошли
            return 0
       
        if bit_pos == 0:# если же читаем новый байт
            current_byte = encoded_data[byte_index]
            byte_index += 1
        
        bit = (current_byte >> (7 - bit_pos)) & 1# извлекаем бит из текущего байта и определяем позицию
        bit_pos = (bit_pos + 1) % 8# увеличиваем е1
        
        return bit
    
    low = 0
    high = MAX_VAL
    value = 0# текущее значение
    
    for i in range(16):# читаем первые 16
        value = (value << 1) | read_bit()
    
    result = bytearray()

    for i in range(original_length):# декод заданного 
        range_size = high - low + 1 # размер интервала
        freq = ((value - low + 1) * total - 1) // range_size # восстановление частоты
    
        idx = 0
        while idx < len(c_summa) - 1 and freq >= c_summa[idx + 1]:# ищем интервалы 
            idx += 1
        
        sym = symbols[idx]# получаем символ по индексу
        result.append(sym[0])
        
        # границы интервала этого символа
        sym_low = c_summa[idx]
        sym_high = c_summa[idx + 1]
        
        #сужение интервала
        high = low + (range_size * sym_high) // total - 1
        low = low + (range_size * sym_low) // total
       
        while True:# масштабирование
            
            if low >= HALF_VAL:#1) в верхней половине
                low -= HALF_VAL
                high -= HALF_VAL
                value -= HALF_VAL

            elif low >= Q1_VAL and high < Q3_VAL:#2) в средней
                low -= Q1_VAL
                high -= Q1_VAL
                value -= Q1_VAL

            elif not high < HALF_VAL: #3) в нижней
                break
            
            low <<= 1# расширяем интервал
            high = (high << 1) | 1
            value = (value << 1) | read_bit()
    
    return bytes(result)

#читает файл, сжимает, сохраняет
def compress_file(in_file, out_file):
    print(f"Сжатие: {in_file} -> {out_file}")
    
    try:
        with open(in_file, 'rb') as f:
            data = f.read()
    except:
        print("Ошибка чтения")
        return False
    
    if not data:
        open(out_file, 'wb').close()
        print("Файл пуст")
        return True
    
    symbols, freqs, coded = arithmetic_encode(data)
    
    with open(out_file, 'wb') as f:
        f.write(len(symbols).to_bytes(2, 'little'))
        f.write(len(data).to_bytes(4, 'little'))
        for i in range(len(symbols)):
            f.write(symbols[i]) 
            f.write(freqs[i].to_bytes(4, 'little'))
        f.write(coded)

    orig_size = len(data)
    comp_size = 2 + 4 + len(symbols) * 5 + len(coded)
    
    print(f"Исходный размер: {orig_size} байт")
    print(f"Сжатый размер: {comp_size} байт")
    
    if orig_size > 0:
        ratio = (orig_size - comp_size) / orig_size * 100
        print(f"Степень сжатия: {ratio:.1f}%")
    
    return True

#читает сжатый файл, распаковывает
def decompress_file(in_file, out_file):
    print(f"Распаковка: {in_file} -> {out_file}")
    
    try:
        with open(in_file, 'rb') as f:
            sym_count = int.from_bytes(f.read(2), 'little')
            data_len = int.from_bytes(f.read(4), 'little')
            
            symbols = []
            freqs = []
            for i in range(sym_count):
                sym = f.read(1)
                freq = int.from_bytes(f.read(4), 'little')
                symbols.append(sym)
                freqs.append(freq)

            coded = f.read()
        
        result = arithmetic_decode(symbols, freqs, coded, data_len)
        
        if len(result) != data_len:
            print(f"Ошибка: ожидалось {data_len} байт, получено {len(result)}")
            return False
        
        with open(out_file, 'wb') as f:
            f.write(result)
        
        print(f"Распаковано: {len(result)} байт")
        return True
        
    except Exception as e:
        print(f"Ошибка распаковки: {e}")
        return False

def main():
    if len(sys.argv) < 4:
        print("  python lab2.py compress file.txt file.bin")
        print("  python lab2.py decompress file.bin file1.txt")
        return 1
    
    cmd = sys.argv[1].lower()
    inp = sys.argv[2]
    out = sys.argv[3]
    
    if not os.path.exists(inp):
        print(f"Файл {inp} не найден")
        return 1
    
    if cmd == "compress":
        success = compress_file(inp, out)
    elif cmd == "decompress":
        success = decompress_file(inp, out)
    else:
        print("compress или decompress")
        return 1
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
    
 

