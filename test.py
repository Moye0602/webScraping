# dict = {}
# chars = ["a","a","b","b","c","c","c"]
# chars = ["a"]
# chars = ["a","b","b","b","b","b","b","b","b","b","b","b","b"]
# for L in chars:
    
#     charsB = chars[chars.index(L):]
#     for r in charsB:
#         dict[L] = dict.get(L,0) + 1
#         break

    
#     # for r in chars:
# print(dict)
# string =''
# for k,v in dict.items():
#     if v >1:
#         string += f"{k}{v}"
#     else:
#         string += f"{k}"

# print(string)

l1 = [2,4,3]
l2 = [5,6,4]
# l1 = [0]
# l2 = [0]
l1.reverse()
l2.reverse()
# l1 = [9,9,9,9,9,9,9]
# l2 = [9,9,9,9]

l3 = []
l3 = [(l1[i] +l2[i])%10 for i in range( max( len(l1), len(l2) ) )]
    
print(l3)
    
