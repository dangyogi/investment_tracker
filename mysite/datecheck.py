# datecheck.py

from time import asctime, localtime, gmtime, strptime
import calendar


print("Apr 9, 2007 - localtime", asctime(localtime(1176163200)))
print("Apr 9, 2007 - gmtime", asctime(gmtime(1176163200)))

print("Apr 17, 2020 - localtime", asctime(localtime(1587168000)))
print("Apr 17, 2020 - gmtime", asctime(gmtime(1587168000)))


print("Apr 9, 2007", calendar.timegm(strptime("Apr-9-2007", "%b-%d-%Y")))
print("Apr 10, 2007", calendar.timegm(strptime("Apr-10-2007", "%b-%d-%Y")))
